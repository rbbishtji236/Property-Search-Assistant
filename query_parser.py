
import os
import json
import re
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()


class PropertyFilters(BaseModel):

    bhk: Optional[str] = Field(
        None, description="BHK type like '1', '2', '3', '4'")
    city: Optional[str] = Field(
        None, description="City name in lowercase like 'pune', 'mumbai'")
    max_price_cr: Optional[float] = Field(
        None, description="Maximum price in Crores")
    min_price_cr: Optional[float] = Field(
        None, description="Minimum price in Crores")
    status: Optional[str] = Field(
        None, description="Property status: 'READY_TO_MOVE' or 'UNDER_CONSTRUCTION'")
    furnished: Optional[str] = Field(
        None, description="Furnishing type: 'FURNISHED', 'SEMI_FURNISHED', or 'UNFURNISHED'")
    locality: Optional[str] = Field(
        None, description="Locality/area name in lowercase")
    min_area: Optional[int] = Field(
        None, description="Minimum carpet area in square feet")
    bathrooms: Optional[int] = Field(
        None, description="Minimum number of bathrooms")


def get_column_schema():
    return {
        "projectName": "Name of the property project",
        "type": "BHK type - can be 1BHK, 2BHK, 3BHK, 4BHK, 5BHK, etc.",
        "price": "Property price in rupees (number)",
        "price_cr": "Property price in Crores (derived from price)",
        "price_lakhs": "Property price in Lakhs (derived from price)",
        "carpetArea": "Carpet area in square feet (number)",
        "cityId": "City identifier - needs to be mapped",
        "localityId": "Locality identifier",
        "landmark": "Landmark or area name (string)",
        "status": "Property status - READY_TO_MOVE or UNDER_CONSTRUCTION",
        "furnishedType": "Furnishing - FURNISHED, SEMI_FURNISHED, or UNFURNISHED",
        "bathrooms": "Number of bathrooms (number)",
        "balcony": "Number of balconies (number)",
        "lift": "Whether lift is available (true/false)",
        "parkingType": "Type of parking available",
        "possessionDate": "When property will be ready (date)",

        # Cities mapping
        "cities": {
            "mumbai": "cmf6nu3ru000gvcxspxarll3v",
            "pune": "cmf50r5a00000vcj0k1iuocuu"
        }
    }


def create_langchain_prompt():
    schema = get_column_schema()

    template = """You are a property search assistant AI. Extract search filters from the user's query.

Available Database Columns:
{schema}

EXTRACTION RULES:
1. BHK: Extract from patterns like "3BHK", "2 bedroom", "three bhk" → return as string "1", "2", "3", etc.
2. City: Extract city name → return lowercase: "mumbai", "pune", "bangalore", "delhi"
3. Price Conversions:
   - "under 1.2 crore" → max_price_cr: 1.2
   - "below 80 lakhs" → max_price_cr: 0.8 (convert lakhs to crores by dividing by 100)
   - "between 1 to 2 crore" → min_price_cr: 1.0, max_price_cr: 2.0
   - "above 50 lakhs" → min_price_cr: 0.5
4. Status: 
   - "ready to move", "immediate possession" → "READY_TO_MOVE"
   - "under construction", "upcoming" → "UNDER_CONSTRUCTION"
5. Furnished: 
   - "furnished" → "FURNISHED"
   - "semi furnished" → "SEMI_FURNISHED"
   - "unfurnished" → "UNFURNISHED"
6. Locality: Extract area/landmark names like "Wakad", "Baner" → return lowercase
7. Area: "above 1000 sqft", "more than 1000 square feet" → min_area: 1000
8. Bathrooms: "2 bathrooms", "at least 2 bath" → bathrooms: 2

User Query: "{query}"

{format_instructions}

Extract all relevant filters and return ONLY valid JSON. If a filter is not mentioned, omit it from the output.

JSON Output:"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["query", "schema"],
        partial_variables={
            "schema": json.dumps(schema, indent=2),
            "format_instructions": "Return a JSON object with the extracted filters."
        }
    )

    return prompt


def initialize_langchain_llm():

    api_key = os.getenv('HUGGINGFACE_API_KEY')
    model_name = os.getenv(
        'HF_MODEL_NAME', 'meta-llama/Meta-Llama-3-8B-Instruct')

    if not api_key or api_key == 'your_huggingface_api_key_here':
        raise ValueError("HUGGINGFACE_API_KEY not found in .env file")

    print(f"Initializing LangChain with {model_name}...")

    llm = HuggingFaceEndpoint(
        repo_id=model_name,
        huggingfacehub_api_token=api_key,
        temperature=0.1,
        max_new_tokens=300,
        top_p=0.9,
        repetition_penalty=1.1
    )

    return llm


def create_extraction_chain():

    llm = initialize_langchain_llm()
    prompt = create_langchain_prompt()

    chain = LLMChain(
        llm=llm,
        prompt=prompt,
        verbose=False 
    )

    return chain


def extract_json_from_response(text):
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed = json.loads(json_str)

            parsed = {k: v for k, v in parsed.items() if v is not None}

            return parsed

        parsed = json.loads(text)
        return {k: v for k, v in parsed.items() if v is not None}

    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from response: {e}")
        print(f" Response was: {text[:200]}...")
        return {}


def parse_user_query(query, use_llm=True):

    print(f"\n Parsing query: '{query}'")

    if not use_llm:
        print("LLM disabled, using fallback regex parsing")
        return parse_user_query_regex(query)

    try:
        api_key = os.getenv('HUGGINGFACE_API_KEY')
        if not api_key or api_key == 'your_huggingface_api_key_here':
            print("Error: HUGGINGFACE_API_KEY not found in .env file")
            print("Falling back to regex-based parsing...")
            return parse_user_query_regex(query)

        chain = create_extraction_chain()

        print("Running LangChain extraction...")

        response = chain.invoke({
            "query": query,
            "schema": json.dumps(get_column_schema(), indent=2)
        })

        response_text = response.get('text', '') if isinstance(
            response, dict) else str(response)

        print(f"LangChain response received")

        filters = extract_json_from_response(response_text)

        if filters:
            print(f"Extracted filters: {json.dumps(filters, indent=2)}")
        else:
            print("No filters extracted, trying regex fallback...")
            filters = parse_user_query_regex(query)

        return filters

    except Exception as e:
        print(f"Error during LangChain parsing: {e}")
        print("   Falling back to regex-based parsing...")
        return parse_user_query_regex(query)


def parse_user_query_regex(query):
    query_lower = query.lower()
    filters = {}

    print("Using regex fallback parser...")

    # Extract BHK
    match = re.search(r'(\d)\s*bhk', query_lower)
    if not match:
        match = re.search(r'(\d)\s*bedroom', query_lower)
    if match:
        filters['bhk'] = match.group(1)
        print(f"   ✓ Found BHK: {filters['bhk']}")

    cities = ['mumbai', 'pune', 'bangalore', 'bengaluru', 'delhi', 'hyderabad',
              'chennai', 'kolkata', 'ahmedabad', 'gurgaon', 'gurugram', 'noida']
    for city in cities:
        if city in query_lower:
            filters['city'] = 'bangalore' if city == 'bengaluru' else city
            print(f" Found City: {filters['city'].title()}")
            break

    match = re.search(
        r'(?:under|below|less than|upto|up to)\s+(?:₹|rs\.?)?\s*(\d+\.?\d*)\s*(?:crore?|cr)', query_lower, re.IGNORECASE)
    if match:
        filters['max_price_cr'] = float(match.group(1))
        print(f"  Found Max Price: ₹{filters['max_price_cr']} Cr")

    match = re.search(
        r'(?:under|below|less than|upto|up to)\s+(?:₹|rs\.?)?\s*(\d+\.?\d*)\s*(?:lakh?|lac)', query_lower, re.IGNORECASE)
    if match:
        filters['max_price_cr'] = float(match.group(1)) / 100
        print(
            f" Found Max Price: ₹{filters['max_price_cr']} Cr (converted from lakhs)")

    match = re.search(
        r'(?:above|more than|over|minimum)\s+(?:₹|rs\.?)?\s*(\d+\.?\d*)\s*(?:crore?|cr)', query_lower, re.IGNORECASE)
    if match:
        filters['min_price_cr'] = float(match.group(1))
        print(f" Found Min Price: ₹{filters['min_price_cr']} Cr")

    match = re.search(
        r'between\s+(?:₹|rs\.?)?\s*(\d+\.?\d*)\s*(?:to|and|-)\s*(\d+\.?\d*)\s*(?:crore?|cr)', query_lower, re.IGNORECASE)
    if match:
        filters['min_price_cr'] = float(match.group(1))
        filters['max_price_cr'] = float(match.group(2))
        print(
            f" Found Price Range: ₹{filters['min_price_cr']} - ₹{filters['max_price_cr']} Cr")

    if 'ready to move' in query_lower or 'ready' in query_lower:
        filters['status'] = 'READY_TO_MOVE'
        print(f"  Found Status: READY_TO_MOVE")
    elif 'under construction' in query_lower or 'construction' in query_lower:
        filters['status'] = 'UNDER_CONSTRUCTION'
        print(f"  Found Status: UNDER_CONSTRUCTION")

    if 'semi furnished' in query_lower or 'semi-furnished' in query_lower:
        filters['furnished'] = 'SEMI_FURNISHED'
        print(f"  Found Furnishing: SEMI_FURNISHED")
    elif 'unfurnished' in query_lower:
        filters['furnished'] = 'UNFURNISHED'
        print(f"  Found Furnishing: UNFURNISHED")
    elif 'furnished' in query_lower:
        filters['furnished'] = 'FURNISHED'
        print(f"  Found Furnishing: FURNISHED")

    match = re.search(
        r'(?:near|in|at|around)\s+([A-Za-z\s]+?)(?:\s+area|\s+locality|,|\s+under|\s+below|$)', query_lower)
    if match:
        locality = match.group(1).strip()
        exclude_words = ['the', 'a', 'an', 'with',
                         'property', 'flat', 'apartment']
        if locality not in exclude_words and len(locality) > 2:
            filters['locality'] = locality
            print(f"  Found Locality: {locality.title()}")

    match = re.search(
        r'(?:above|more than|over|minimum)\s+(\d+)\s*(?:sqft|sq\.?\s*ft|square feet)', query_lower, re.IGNORECASE)
    if match:
        filters['min_area'] = int(match.group(1))
        print(f"  Found Min Area: {filters['min_area']} sq.ft")

    return filters


def get_query_intent(query):

    query = query.lower()

    greetings = ['hi', 'hello', 'hey', 'good morning', 'good evening']
    if any(greeting in query for greeting in greetings):
        return 'greeting'

    help_keywords = ['help', 'how to', 'what can you', 'guide']
    if any(keyword in query for keyword in help_keywords):
        return 'help'

    search_keywords = ['find', 'show', 'search', 'looking', 'want', 'need',
                       'bhk', 'flat', 'apartment', 'property', 'home']
    if any(keyword in query for keyword in search_keywords):
        return 'search'

    return 'search'

if __name__ == "__main__":

    api_key = os.getenv('HUGGINGFACE_API_KEY')
    if not api_key or api_key == 'your_huggingface_api_key_here':
        print("\n WARNING: API_KEY not found")
    test_queries = [
        "3BHK flat in Pune under ₹1.2 Cr",
        "Show me 2 bedroom apartments in Mumbai below 80 lakhs",
        "Ready to move 3BHK near Wakad",
        "Furnished 2BHK in Delhi under 90 lakhs",
        "Properties between 1 to 2 crore in Bangalore",
    ]

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: '{query}'")
        print(f"Intent: {get_query_intent(query)}")
        filters = parse_user_query(query, use_llm=True)
        print()
