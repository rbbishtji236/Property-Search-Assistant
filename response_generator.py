import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

load_dotenv()


def initialize_summary_llm():
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    model_name = os.getenv('HF_MODEL_NAME', 'meta-llama/Meta-Llama-3-8B-Instruct')
    
    if not api_key or api_key == 'your_huggingface_api_key_here':
        return None
    
    llm = HuggingFaceEndpoint(
        repo_id=model_name,
        huggingfacehub_api_token=api_key,
        temperature=0.3,
        max_new_tokens=200,
        top_p=0.9
    )
    
    return llm


def create_summary_prompt():
    template = """You are a helpful property search assistant. Generate a natural, conversational summary of property search results.

Search Statistics:
- Total properties found: {total_count}
- BHK types: {bhk_types}
- Price range: ₹{min_price:.2f} Cr to ₹{max_price:.2f} Cr
- Average price: ₹{avg_price:.2f} Cr
- Top localities: {localities}
- Status: {ready_count} ready to move, {construction_count} under construction
- Average carpet area: {avg_area:.0f} sq.ft

User's original query: "{user_query}"

RULES for summary:
1. Keep it conversational and helpful (3-4 sentences max)
2. Mention the total count and BHK type if specified
3. Mention price range and average
4. Highlight top 2-3 localities
5. Mention ready vs under construction split
6. If no results, suggest expanding search criteria
7. Be positive and encouraging

Generate a natural summary (3-4 sentences only):"""

    prompt = PromptTemplate(
        template=template,
        input_variables=[
            "total_count", "bhk_types", "min_price", "max_price", 
            "avg_price", "localities", "ready_count", "construction_count",
            "avg_area", "user_query"
        ]
    )
    
    return prompt


def generate_summary_with_llm(stats, user_query):
    try:
        llm = initialize_summary_llm()
        
        if not llm:
            return generate_summary_template(stats, user_query)
        
        prompt = create_summary_prompt()
        chain = LLMChain(llm=llm, prompt=prompt, verbose=False)
        
        input_data = {
            "total_count": stats.get('total_count', 0),
            "bhk_types": ", ".join(stats.get('bhk_types', [])),
            "min_price": stats.get('min_price_cr', 0),
            "max_price": stats.get('max_price_cr', 0),
            "avg_price": stats.get('avg_price_cr', 0),
            "localities": ", ".join(stats.get('localities', [])[:3]),
            "ready_count": stats.get('status_distribution', {}).get('READY_TO_MOVE', 0),
            "construction_count": stats.get('status_distribution', {}).get('UNDER_CONSTRUCTION', 0),
            "avg_area": stats.get('avg_area', 0),
            "user_query": user_query
        }
        
        print("Generating summary with LangChain...")
        response = chain.invoke(input_data)
        
        summary = response.get('text', '') if isinstance(response, dict) else str(response)
        summary = summary.strip()
        
        if summary:
            return summary
        else:
            return generate_summary_template(stats, user_query)
            
    except Exception as e:
        print(f"LLM summary generation failed: {e}")
        print("Using template-based fallback...")
        return generate_summary_template(stats, user_query)


def generate_summary_template(stats, user_query):
    
    total = stats.get('total_count', 0)
    
    if total == 0:
        return (
            "No properties found matching your exact criteria. "
            "Try adjusting your budget, location, or property type for more options."
        )
    
    summary_parts = []
    
    bhk_types = stats.get('bhk_types', [])
    if bhk_types and len(bhk_types) == 1:
        summary_parts.append(f"Found {total} {bhk_types[0]} properties")
    elif bhk_types:
        summary_parts.append(f"Found {total} properties ({', '.join(bhk_types)})")
    else:
        summary_parts.append(f"Found {total} properties")
    
    localities = stats.get('localities', [])[:3]
    if localities:
        if len(localities) == 1:
            summary_parts.append(f"in {localities[0]}")
        elif len(localities) == 2:
            summary_parts.append(f"in {localities[0]} and {localities[1]}")
        else:
            summary_parts.append(f"in {', '.join(localities[:-1])}, and {localities[-1]}")
    
    avg_price = stats.get('avg_price_cr', 0)
    min_price = stats.get('min_price_cr', 0)
    max_price = stats.get('max_price_cr', 0)
    
    if avg_price > 0:
        if avg_price >= 1:
            summary_parts.append(f"averaging ₹{avg_price:.2f} Cr")
        else:
            summary_parts.append(f"averaging ₹{avg_price*100:.0f} Lakhs")
    
    first_sentence = " ".join(summary_parts) + "."
    
    status_dist = stats.get('status_distribution', {})
    ready = status_dist.get('READY_TO_MOVE', 0)
    construction = status_dist.get('UNDER_CONSTRUCTION', 0)
    
    status_parts = []
    if ready > 0:
        status_parts.append(f"{ready} ready to move")
    if construction > 0:
        status_parts.append(f"{construction} under construction")
    
    if status_parts:
        second_sentence = " and ".join(status_parts).capitalize() + "."
    else:
        second_sentence = ""
    
    if min_price > 0 and max_price > 0 and min_price != max_price:
        if max_price >= 1:
            price_sentence = f"Prices range from ₹{min_price:.2f} Cr to ₹{max_price:.2f} Cr."
        else:
            price_sentence = f"Prices range from ₹{min_price*100:.0f} Lakhs to ₹{max_price*100:.0f} Lakhs."
    else:
        price_sentence = ""
    
    summary = f"{first_sentence} {second_sentence} {price_sentence}".strip()
    
    return summary


def generate_response(search_results, search_stats, user_query, filters, use_llm=True):
    
    print("\n Generating response...")
    
    if use_llm:
        summary = generate_summary_with_llm(search_stats, user_query)
    else:
        summary = generate_summary_template(search_stats, user_query)
    
    print(f"Summary generated: {len(summary)} characters")
    
    cards = format_property_cards(search_results)
    
    response = {
        'summary': summary,
        'total_count': search_stats.get('total_count', 0),
        'cards': cards,
        'stats': search_stats,
        'filters_used': filters
    }
    
    return response


def format_property_cards(df, max_cards=10):
    if len(df) == 0:
        return []
    
    cards = []
    
    for idx, row in df.head(max_cards).iterrows():
        if row['price_cr'] >= 1:
            price_display = f"₹{row['price_cr']:.2f} Cr"
        else:
            price_display = f"₹{row['price_lakhs']:.0f} Lakhs"
        

        status_display = 'Ready to Move' if row['status'] == 'READY_TO_MOVE' else 'Under Construction'
        
     
        area_display = f"{row['carpetArea']:.0f} sq.ft" if row['carpetArea'] > 0 else "N/A"
     
        card = {
            'title': row.get('display_name', row['projectName']),
            'project_name': row['projectName'],
            'bhk': row['type'],
            'price': row['price'],
            'price_display': price_display,
            'carpet_area': row['carpetArea'],
            'area_display': area_display,
            'locality': row['landmark'],
            'status': row['status'],
            'status_display': status_display,
            'status_emoji': '✅' if row['status'] == 'READY_TO_MOVE' else 'under Construction',
            'furnished': row.get('furnishedType', 'Not specified'),
            'bathrooms': int(row['bathrooms']) if row['bathrooms'] > 0 else 'N/A',
            'balcony': int(row.get('balcony', 0)) if row.get('balcony', 0) > 0 else 'N/A',
            'lift': 'Yes' if str(row.get('lift', '')).lower() == 'true' else 'No',
            'parking': row.get('parkingType', 'N/A') if row.get('parkingType') else 'N/A',
            'possession_date': row.get('possessionDate', 'N/A'),
            'slug': row.get('slug', ''),
            'url': f"/project/{row.get('slug', '')}"
        }
        
        cards.append(card)
    
    return cards


def format_greeting_response():
    return {
        'summary': (
            "👋 Hello! I'm your property search assistant. "
            "I can help you find properties based on your preferences. "
            "Try asking me something like: '3BHK flat in Pune under ₹1.2 Cr' or "
            "'Show me ready to move 2BHK apartments in Mumbai'."
        ),
        'total_count': 0,
        'cards': [],
        'is_greeting': True
    }


def format_help_response():
    return {
        'summary': (
            "🤔 Here's what I can help you with:\n\n"
            "**Search by:**\n"
            "• BHK type: '3BHK', '2 bedroom'\n"
            "• City: 'Pune', 'Mumbai', 'Bangalore'\n"
            "• Budget: 'under 1.5 crore', 'below 80 lakhs'\n"
            "• Status: 'ready to move', 'under construction'\n"
            "• Area: 'near Wakad', 'in Baner'\n"
            "• Furnishing: 'furnished', 'unfurnished'\n\n"
            "**Example queries:**\n"
            "• 3BHK flat in Pune under ₹1.2 Cr\n"
            "• Ready to move 2BHK in Mumbai below 80 lakhs\n"
            "• Furnished apartments near Wakad"
        ),
        'total_count': 0,
        'cards': [],
        'is_help': True
    }


def format_no_results_response(filters, user_query):
    suggestions = []
    
    if 'max_price_cr' in filters:
        new_budget = filters['max_price_cr'] * 1.3
        suggestions.append(f"• Increase budget to ₹{new_budget:.2f} Cr")
    
    if 'locality' in filters:
        suggestions.append(f"• Try nearby areas instead of {filters['locality']}")
    
    if 'bhk' in filters:
        suggestions.append(f"• Consider {int(filters['bhk'])-1}BHK or {int(filters['bhk'])+1}BHK options")
    
    if 'status' in filters:
        suggestions.append("• Include both ready and under construction properties")
    
    if not suggestions:
        suggestions = [
            "• Try a different city or locality",
            "• Adjust your budget range",
            "• Consider different BHK types"
        ]
    
    suggestion_text = "\n".join(suggestions)
    
    return {
        'summary': (
            f"😕 No properties found matching your exact criteria.\n\n"
            f"**Try these suggestions:**\n{suggestion_text}"
        ),
        'total_count': 0,
        'cards': [],
        'filters_used': filters,
        'is_no_results': True
    }


if __name__ == "__main__":

    from data_loader import load_and_merge_data
    from search_engine import search_properties, get_search_statistics
    
    print("\n Loading data...")
    df = load_and_merge_data()
    
    print("\n" + "=" * 80)
    print("TEST CASE 1: Generate response for successful search")
    print("=" * 80)
    
    filters1 = {'bhk': '3', 'city': 'pune', 'max_price_cr': 1.5}
    user_query1 = "3BHK flat in Pune under 1.5 crore"
    
    results1 = search_properties(df, filters1, max_results=5)
    stats1 = get_search_statistics(results1, filters1)
    
    response1 = generate_response(results1, stats1, user_query1, filters1, use_llm=True)
    
    print(f"\n Summary:")
    print(response1['summary'])
    
    print(f"\n Property Cards: {len(response1['cards'])}")
    if response1['cards']:
        card = response1['cards'][0]
        print(f"\n   Sample Card:")
        print(f"    {card['title']}")
        print(f"    {card['locality']}")
        print(f"    {card['price_display']}")
        print(f"    {card['area_display']}")
        print(f"   {card['status_emoji']} {card['status_display']}")
    
    print("\n" + "=" * 80)
    print("TEST CASE 2: No results response")
    print("=" * 80)
    
    filters2 = {'bhk': '5', 'max_price_cr': 0.5}
    response2 = format_no_results_response(filters2, "5BHK under 50 lakhs")
    
    print(f"\n Summary:")
    print(response2['summary'])
    
    print("\n" + "=" * 80)
    print("TEST CASE 3: Greeting response")
    print("=" * 80)
    
    response3 = format_greeting_response()
    print(f"\n Summary:")
    print(response3['summary'])
    
    print("\n" + "=" * 80)
    print("TEST CASE 4: Help response")
    print("=" * 80)
    
    response4 = format_help_response()
    print(f"\n Summary:")
    print(response4['summary'])
    
    print("\n" + "=" * 80)
    print("Response Generator Complete")