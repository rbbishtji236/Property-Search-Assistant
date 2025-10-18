import streamlit as st
import pandas as pd
from datetime import datetime

from data_loader import load_and_merge_data
from query_parser import parse_user_query, get_query_intent
from search_engine import search_properties, get_search_statistics, expand_search_if_needed
from response_generator import (
    generate_response, 
    format_greeting_response, 
    format_help_response,
    format_no_results_response
)


max_results=5


# CSS for better UI
st.markdown("""
<style>
    /* Main chat container */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* Property cards */
    .property-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        background-color: #f9f9f9;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .property-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .property-title {
        font-size: 1.3rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    
    .property-price {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2ca02c;
        margin: 0.5rem 0;
    }
    
    .property-detail {
        display: inline-block;
        margin-right: 1.5rem;
        color: #555;
    }
    
    .property-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.85rem;
        margin-right: 0.5rem;
    }
    
    .badge-ready {
        background-color: #d4edda;
        color: #155724;
    }
    
    .badge-construction {
        background-color: #fff3cd;
        color: #856404;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* Search stats */
    .search-stats {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_property_data():
    return load_and_merge_data()


def initialize_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'property_data' not in st.session_state:
        with st.spinner("🔄 Loading property database..."):
            st.session_state.property_data = load_property_data()
    
    if 'search_count' not in st.session_state:
        st.session_state.search_count = 0


def display_property_card(card):
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"{card['title']}")
            
            st.markdown(f"**{card['locality']}**")
        
        with col2:
            st.markdown(f"<div style='text-align: right;'><h3 style='color: #2ca02c; margin: 0;'>{card['price_display']}</h3></div>", unsafe_allow_html=True)
        
        col_badge1, col_badge2, col_badge3 = st.columns([1, 1, 2])
        
        with col_badge1:
            if card['status'] == 'READY_TO_MOVE':
                st.success(f"Ready to Move")
            else:
                st.warning(f"Under Construction")
        
        with col_badge2:
            st.info(f"{card['furnished']}")
        
        detail_cols = st.columns(4)
        
        with detail_cols[0]:
            st.metric("Area", card['area_display'])
        
        with detail_cols[1]:
            st.metric("Bathrooms", card['bathrooms'])
        
        with detail_cols[2]:
            st.metric("Lift", card['lift'])
        
        with detail_cols[3]:
            if card.get('balcony', 'N/A') != 'N/A':
                st.metric("Balcony", card['balcony'])
    
        st.caption(f"**Project:** {card['project_name']}")

        st.divider()


def display_search_stats(stats):
    
    st.markdown("#### Search Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Properties",
            value=stats.get('total_count', 0)
        )
    
    with col2:
        avg_price = stats.get('avg_price_cr', 0)
        st.metric(
            label="Avg Price",
            value=f"₹{avg_price:.2f} Cr"
        )
    
    with col3:
        min_price = stats.get('min_price_cr', 0)
        max_price = stats.get('max_price_cr', 0)
        st.metric(
            label="Price Range",
            value=f"₹{min_price:.2f} - {max_price:.2f} Cr"
        )
    
    with col4:
        avg_area = stats.get('avg_area', 0)
        st.metric(
            label="Avg Area",
            value=f"{avg_area:.0f} sq.ft"
        )
    
    st.markdown("---")


def process_user_query(user_input):
 
    intent = get_query_intent(user_input)
    
    if intent == 'greeting':
        return format_greeting_response()
    
    elif intent == 'help':
        return format_help_response()
    
    else:  
        with st.spinner("Understanding your query..."):
            filters = parse_user_query(user_input, use_llm=True)
    
        with st.spinner("Searching properties..."):
            df = st.session_state.property_data
            results = search_properties(df, filters, max_results=5)
            if len(results) < 3:
                results, expansion_msg = expand_search_if_needed(results, filters, df)
                if expansion_msg:
                    st.info(f"{expansion_msg}")
            
            stats = get_search_statistics(results, filters)
      
        if len(results) == 0:
            return format_no_results_response(filters, user_input)
        
        with st.spinner("✨ Generating response..."):
            response = generate_response(results, stats, user_input, filters, use_llm=True)
        
        st.session_state.search_count += 1
        
        return response


def render_sidebar():
    
    with st.sidebar:
        st.subheader("Property Search Assistant")
        
        st.markdown("---")
        st.markdown("### Example Queries")
        examples = [
            "3BHK flat in Pune under ₹1.2 Cr",
            "Ready to move 2BHK in Mumbai",
            "Furnished apartments near Wakad",
            "Properties between 1 to 2 crore",
            "Show me 4BHK above 2 crore"
        ]
        
        for example in examples:
            if st.button(example, key=example, use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": example,
                    "timestamp": datetime.now()
                })
                response = process_user_query(example)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now()
                })
                st.rerun()
        
        st.markdown("---")
        
        st.markdown("###Settings")
        
        use_llm = st.checkbox("Use AI for parsing", value=True, 
                             help="Uses LLM for query understanding. Disable for faster but less accurate parsing.")
        
        show_stats = st.checkbox("Show search statistics", value=True,
                                help="Display detailed statistics for each search")
        
        st.session_state.use_llm = use_llm
        st.session_state.show_stats = show_stats
        st.session_state.max_results = max_results
        
        st.markdown("---")
        
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.search_count = 0
            st.rerun()
        
        st.markdown("---")


def main():
    initialize_session_state()
    
    render_sidebar()
    
    st.title("Property Search Chatbot")
    st.markdown("Ask me anything about properties! Try: *'3BHK flat in Pune under ₹1.2 Cr'*")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                response = message["content"]
               
                st.markdown(response['summary'])
              
                if st.session_state.get('show_stats', True) and 'stats' in response:
                    display_search_stats(response['stats'])
                
                if response.get('cards'):
                    st.markdown(f"### Found {len(response['cards'])} Properties")
                    
                    for card in response['cards']:
                        display_property_card(card)
  
    if prompt := st.chat_input("Ask about properties... (e.g., '3BHK in Pune under 1.2 Cr')"):
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now()
        })
        
        with st.chat_message("user"):
            st.write(prompt)
        
        with st.chat_message("assistant"):
            response = process_user_query(prompt)
         
            st.markdown(response['summary'])
           
            if st.session_state.get('show_stats', True) and 'stats' in response:
                display_search_stats(response['stats'])
           
            if response.get('cards'):
                st.markdown(f"### Found {len(response['cards'])} Properties")
                
                for card in response['cards']:
                    display_property_card(card)
       
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })


if __name__ == "__main__":
    main()