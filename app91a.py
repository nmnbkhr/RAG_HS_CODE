import os
import requests
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.agents import create_react_agent, AgentExecutor, Tool

# Load environment variables from .env file
load_dotenv()

# Get and validate API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip()  # Remove any whitespace
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY  # Update environment

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
FAISS_INDEX_PATH = "faiss_index"
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/PKR"

# Function to fetch exchange rate
def get_exchange_rate(from_currency):
    try:
        response = requests.get(EXCHANGE_RATE_API)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            return rates.get(from_currency, 1.0)
        else:
            st.warning("Failed to fetch exchange rates. Using PKR as default.")
            return 1.0
    except Exception as e:
        st.warning(f"Error fetching exchange rates: {e}. Using PKR as default.")
        return 1.0

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
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables.")
        return None
    
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
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

        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        st.success("Built and saved new FAISS index.")
        return vectorstore

# Set up RAG chain
def setup_qa_chain(vectorstore):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables.")
        return None
    llm = ChatOpenAI(temperature=0.5, openai_api_key=api_key)  # Increased for fuzzy matching

    prompt_template = """Use the following HS code context to answer the question. Provide the exact HS/PCT code, description, and any duty rates or notes (including whether duty is ad valorem (%) or specific (e.g., PKR/kg)). If classifying an item, match it to the closest heading/subheading using fuzzy matching for vague terms. If the item is ambiguous or complex, return a markdown table in the format below, followed by a clarification request:

    | HS Code | Description | Duty |
    |---------|-------------|------|
    | [code]  | [desc]      | [duty] |

    Example for 'coal':
    | HS Code | Description | Duty |
    |---------|---------------------------------|-------|
    | 2701.11 | Anthracite, whether or not pulverised, non-agglomerated | 0% |
    | 2701.12 | Bituminous coal, whether or not pulverised, non-agglomerated | 0% |
    | 2701.19 | Other coal | 0% |
    Please specify the type of coal (e.g., anthracite, bituminous, lignite).

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
    query = f"Provide a markdown table of possible HS/PCT codes for '{item_description}' using fuzzy matching. Include HS codes, descriptions, and duties for each possibility, followed by a clarification request. Format as:\n| HS Code | Description | Duty |\n|---------|-------------|------|\n| [code]  | [desc]      | [duty] |\nPlease specify the type of {item_description}."
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
- Evaluate if the query is clear using chat history. If the query is vague, ambiguous, or lacks details (e.g., contains terms like 'coal', 'apples', 'fruits' without specifics):
  1. Thought: Explain why the query is vague (e.g., 'Coal is ambiguous as it has multiple HS codes based on type').
  2. Action: Use Suggest_Possible_HS_Codes to get a markdown table of possible HS codes, descriptions, and duties.
  3. Final Answer: Present the table with a clarification question (e.g., 'Please specify the type of coal (e.g., anthracite, bituminous, lignite).').
- Do not guess or use other tools for vague queries; always use Suggest_Possible_HS_Codes.
- If the query is clear (using chat history to avoid redundant clarification):
  - For a specific HS code query (e.g., 'What is 0101.21?'), use HS_Code_Details and return a descriptive response in Final Answer.
  - For a clear single item classification (e.g., 'Classify fresh apples'), use Classify_Item and provide the HS code, description, and reasoning in Final Answer.
  - For clear multiple items (e.g., 'Classify live horses, cotton t-shirts'), use Classify_Item_List and return a markdown table in Final Answer.
- Use chat history to maintain context (e.g., if user clarified 'bituminous coal', use for follow-ups without asking again).
- For list-based responses, use markdown tables (e.g., | Item | HS Code | Description | Duty | Reasoning |).
- For single-item or code queries, provide detailed text with clear reasoning.
- Stop after one response (clarification with table or final answer); do not loop.

Chat History: {chat_history}

Question: {input}

{agent_scratchpad}
""")

# Streamlit App - Chat Interface and Calculator
st.title("Interactive HS Code Chat Agent & Duty Calculator")

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
api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    st.error("OpenAI API key not set. Please check your .env file at E:\\RAG_HS_Code\\.env or set it manually.")
    st.stop()
else:
    vectorstore = get_vectorstore()
    if vectorstore is None:
        st.error("Failed to initialize vectorstore. Please check your API key and try again.")
        st.stop()
    qa_chain = setup_qa_chain(vectorstore)
    if qa_chain is None:
        st.error("Failed to initialize QA chain. Please check your API key and try again.")
        st.stop()
    st.session_state.qa_chain = qa_chain

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="chat_history", input_key="input")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    llm = ChatOpenAI(temperature=0.5, openai_api_key=api_key)
    agent = create_react_agent(llm, tools, agent_prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=st.session_state.memory,
        verbose=True,
        handle_parsing_errors="Check the query for ambiguity and provide a clarification table with possible HS codes.",
        max_iterations=5,
        max_execution_time=120
    )

    # Tabs for Chat and Calculator
    tab1, tab2 = st.tabs(["Chat Interface", "Duty Calculator"])

    with tab1:
        st.header("Chat with HS Code Agent")
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
                        output = f"Error: {str(e)}"
                        st.error(output)
                        st.session_state.messages.append({"role": "assistant", "content": output})

    with tab2:
        st.header("Duty Calculator")
        st.write("Calculate customs duty based on HS code, quantity, and value.")
        
        hs_code = st.text_input("Enter HS Code (e.g., 0808.10 for fresh apples)", key="calc_hs_code")
        quantity = st.number_input("Enter Quantity", min_value=0.0, step=0.1, key="calc_quantity")
        unit = st.selectbox("Select Unit of Measurement", ["kg", "liters", "units", "tonnes"], key="calc_unit")
        value_per_unit = st.number_input("Enter Value per Unit", min_value=0.0, step=0.1, key="calc_value")
        currency = st.selectbox("Select Currency", ["PKR", "USD", "EUR"], key="calc_currency")
        
        if st.button("Calculate Duty"):
            if not hs_code or quantity <= 0 or value_per_unit <= 0:
                st.error("Please provide a valid HS code, quantity, and value per unit.")
            else:
                with st.spinner("Fetching duty rate..."):
                    try:
                        duty_info = get_hs_code_details(hs_code)
                        duty_rate = None
                        duty_type = None
                        lines = duty_info.split("\n")
                        for line in lines:
                            if "Duty:" in line:
                                duty_text = line.split(":")[1].strip()
                                if "%" in duty_text:
                                    duty_rate = float(duty_text.replace("%", "")) / 100
                                    duty_type = "ad_valorem"
                                elif "PKR" in duty_text:
                                    duty_rate = float(duty_text.replace("PKR", "").split("/")[0].strip())
                                    duty_type = f"specific_{duty_text.split('/')[-1].strip()}"
                                break
                        
                        if duty_rate is None:
                            st.error(f"Could not parse duty rate from: {duty_info}")
                        else:
                            exchange_rate = get_exchange_rate(currency)
                            total_value_pkr = value_per_unit * quantity * exchange_rate
                            
                            if duty_type == "ad_valorem":
                                duty_pkr = total_value_pkr * duty_rate
                            else:
                                if unit == duty_type.split("_")[1]:
                                    duty_pkr = quantity * duty_rate
                                else:
                                    st.error(f"Unit mismatch: Tariff uses {duty_type.split('_')[1]}, but you selected {unit}.")
                                    duty_pkr = None
                            
                            if duty_pkr is not None:
                                st.success(f"""
                                **Duty Calculation Result**  
                                - HS Code: {hs_code}  
                                - Quantity: {quantity} {unit}  
                                - Value per Unit: {value_per_unit} {currency}  
                                - Total Value (PKR): {total_value_pkr:.2f} PKR  
                                - Duty Rate: {duty_text}  
                                - Total Duty: {duty_pkr:.2f} PKR
                                """)
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": f"Duty calculated for HS code {hs_code}: {quantity} {unit} at {value_per_unit} {currency}, total duty {duty_pkr:.2f} PKR."
                                })
                    except Exception as e:
                        st.error(f"Error calculating duty: {str(e)}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Error calculating duty for HS code {hs_code}: {str(e)}"})