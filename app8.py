import os
import requests
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.agents import create_react_agent, AgentExecutor, Tool

# Load environment variables from .env file
load_dotenv()

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
FAISS_INDEX_PATH = "faiss_index"

# Function to check if PDF needs updating and download if necessary
def check_pdf_update(url, local_path):
    try:
        response = requests.head(url)
        if response.status_code == 200:
            last_modified_str = response.headers.get('Last-Modified')
            if last_modified_str:
                remote_date = datetime.strptime(last_modified_str, '%a, %d %b %Y %H:%M:%S GMT')
                if os.path.exists(local_path):
                    local_date = datetime.fromtimestamp(os.path.getmtime(local_path))
                    if remote_date > local_date:
                        download_latest_pdf(url, local_path)
                        return True, "PDF updated to latest version."
                    else:
                        return False, "Local PDF is up-to-date."
                else:
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded (no local file existed)."
            else:
                download_latest_pdf(url, local_path)
                return True, "No Last-Modified header; PDF downloaded."
        else:
            return False, f"Failed to check PDF: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error checking PDF update: {e}"

def download_latest_pdf(url, save_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        st.success(f"Downloaded PDF to {save_path}")
    else:
        raise Exception("Failed to download PDF")

# Function to build or load vector store
@st.cache_resource
def get_vectorstore():
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        st.info("Loaded existing FAISS index.")
        return vectorstore
    else:
        if not os.path.exists(PDF_PATH):
            st.error("PDF not found. Triggering download...")
            check_pdf_update(PDF_URL, PDF_PATH)
        
        loader = PyPDFLoader(PDF_PATH)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.split_documents(documents)

        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        st.success("Built and saved new FAISS index.")
        return vectorstore

# Set up RAG chain
def setup_qa_chain(vectorstore):
    llm = OpenAI(temperature=0.2)

    prompt_template = """Use the following HS code context to answer the question. Provide the exact HS/PCT code, description, and any duty rates or notes. If classifying an item, match it to the closest heading/subheading based on the description. If the item is ambiguous or complex, return a markdown table of possible HS codes with descriptions and duties, and a request for clarification.

    Context: {context}

    Question: {question}

    Answer:"""

    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT}
    )
    return qa_chain

# Tools for the agent
def get_hs_code_details(code):
    qa_chain = st.session_state.qa_chain
    query = f"What is the detailed classification, description, and duty for HS code {code}?"
    result = qa_chain({"query": query})['result']
    return result

def classify_item(item_description):
    qa_chain = st.session_state.qa_chain
    query = f"Classify the item '{item_description}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
    result = qa_chain({"query": query})['result']
    return result

def classify_item_list(items_str):
    qa_chain = st.session_state.qa_chain
    items = [item.strip() for item in items_str.replace(",", "\n").split("\n") if item.strip()]
    if not items:
        return "No valid items provided. Please provide a list of items."
    classifications = []
    for item in items:
        query = f"Classify the item '{item}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
        result = qa_chain({"query": query})['result']
        # Format as markdown table
        lines = result.split("\n")
        hs_code = description = duty = reasoning = "Not found"
        for line in lines:
            if "HS/PCT Code:" in line:
                hs_code = line.split(":")[1].strip()
            elif "Description:" in line:
                description = line.split(":")[1].strip()
            elif "Duty:" in line:
                duty = line.split(":")[1].strip()
            elif "Reasoning:" in line:
                reasoning = line.split(":")[1].strip()
        classifications.append((item, hs_code, description, duty, reasoning))
    
    # Create markdown table
    table = "| Item | HS Code | Description | Duty | Reasoning |\n"
    table += "|------|---------|-------------|------|-----------|\n"
    for item, hs_code, desc, duty, reason in classifications:
        table += f"| {item} | {hs_code} | {desc} | {duty} | {reason} |\n"
    return table

def suggest_possible_hs_codes(item_description):
    qa_chain = st.session_state.qa_chain
    query = f"Provide a markdown table of possible HS/PCT codes for '{item_description}' using fuzzy matching. Include HS codes, descriptions, and duties for each possibility, followed by a clarification request."
    result = qa_chain({"query": query})['result']
    return result

tools = [
    Tool(
        name="HS_Code_Details",
        func=get_hs_code_details,
        description="Use to get detailed information about a specific HS code (e.g., '0101.21'), including classification, description, and duties."
    ),
    Tool(
        name="Classify_Item",
        func=classify_item,
        description="Use to classify a single item (e.g., 'Fresh apples') to its HS/PCT code, providing code, reasoning, and any relevant notes."
    ),
    Tool(
        name="Classify_Item_List",
        func=classify_item_list,
        description="Use to classify a list of items (comma-separated or one per line, e.g., 'Live horses, Cotton t-shirts') to their HS/PCT codes, returning a markdown table."
    ),
    Tool(
        name="Suggest_Possible_HS_Codes",
        func=suggest_possible_hs_codes,
        description="Use to get a markdown table of possible HS/PCT codes, descriptions, and duties for a vague or ambiguous item description, using fuzzy matching, followed by a clarification request."
    ),
]

# Agent prompt with tools and tool_names
agent_prompt = ChatPromptTemplate.from_template("""
You are an HS Code expert assistant. Use the provided tools to answer questions about HS codes and item classifications based on Pakistan's Customs Tariff.

Available tools: {tools}
Tool names: {tool_names}

ReAct Format Reminder:
- Thought: [Your reasoning]
- Action: [If using a tool, specify Action Input]
- Observation: [Tool result]
- ... (Repeat Thought/Action/Observation as needed)
- If no tool is needed or for clarification, go directly to Final Answer after Thought.

Instructions:
- Always evaluate if the query is clear and complete using chat history for context. If the query is complex, ambiguous, or lacks details (e.g., 'Classify coal' or 'What is the code for apples?'):
  1. Thought: Explain why the query is vague (e.g., 'Coal is ambiguous as it has multiple HS codes based on type').
  2. Action: Use Suggest_Possible_HS_Codes to get a markdown table of possible HS codes, descriptions, and duties.
  3. Final Answer: Present the table and ask one clarification question (e.g., 'Please specify the type of coal (e.g., anthracite, bituminous, lignite).').
- Do not guess or use other tools for vague queries; always use Suggest_Possible_HS_Codes for suggestions with fuzzy matching.
- Only if the query is clear (using chat history to avoid redundant clarification):
  - For a specific HS code query (e.g., 'What is 0101.21?'), use HS_Code_Details and return a descriptive response in Final Answer.
  - For a clear single item classification (e.g., 'Classify fresh apples'), use Classify_Item and provide the HS code, description, and reasoning in Final Answer.
  - For clear multiple items (e.g., 'Classify live horses, cotton t-shirts'), use Classify_Item_List and return a markdown table in Final Answer.
- Use chat history to maintain context and build on previous responses (e.g., if user clarified 'bituminous coal' in history, use that for follow-ups without asking again).
- For list-based responses, use markdown tables (e.g., | Item | HS Code | Description | Duty | Reasoning |).
- For single-item or code queries, provide detailed text with clear reasoning.
- If no tool is needed (e.g., clarification or general question), respond directly with a clear explanation or table plus question in Final Answer.
- Stop after one response (either clarification with table or final answer); do not loop unnecessarily.

Chat History: {chat_history}

Question: {input}

{agent_scratchpad}
""")

# Streamlit App - Chat Interface
st.title("Interactive HS Code Chat Agent")

# Sidebar for PDF management
with st.sidebar:
    st.header("PDF Management")
    if st.button("Check/Update PDF"):
        with st.spinner("Checking for updates..."):
            updated, message = check_pdf_update(PDF_URL, PDF_PATH)
            st.info(message)
            if updated:
                if os.path.exists(FAISS_INDEX_PATH):
                    import shutil
                    shutil.rmtree(FAISS_INDEX_PATH)
                st.info("PDF updated. Rebuilding FAISS index...")

    st.markdown("---")
    st.info("Using FY 2024-25 Tariff (latest available as of August 2025). Check FBR for FY 2025-26 updates.")

# Initialize session state
if "OPENAI_API_KEY" not in os.environ:
    st.error("OpenAI API key not set. Please check your .env file at E:\\RAG_HS_Code\\.env or set it manually.")
else:
    vectorstore = get_vectorstore()
    qa_chain = setup_qa_chain(vectorstore)
    st.session_state.qa_chain = qa_chain

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="chat_history", input_key="input")

    llm = OpenAI(temperature=0.3)
    agent = create_react_agent(llm, tools, agent_prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=st.session_state.memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=20,  # Increased from default to handle complex queries
        max_execution_time=300  # 5 minutes timeout
    )

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input
    if prompt := st.chat_input("Ask about HS codes or item classifications (e.g., 'What is HS code 0101.21?', 'Classify fresh apples', 'Classify live horses, cotton t-shirts')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = agent_executor.invoke({"input": prompt})
                    output = response["output"]
                    st.markdown(output)
                    st.session_state.messages.append({"role": "assistant", "content": output})
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})