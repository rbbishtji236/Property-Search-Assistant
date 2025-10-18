
import pandas as pd
from data_loader import get_city_id


def search_properties(df, filters, max_results=10):
    
    print(f"\n Searching properties with filters: {filters}")
   
    results = df.copy()
    
    print(f"   Starting with {len(results)} total properties")

    if 'bhk' in filters:
        bhk = filters['bhk']

        results = results[results['type'].str.contains(bhk, case=False, na=False)]
        print(f"   After BHK filter ({bhk}BHK): {len(results)} properties")
   
    if 'city' in filters:
        city = filters['city']
        city_id = get_city_id(city)
        if city_id:
            results = results[results['cityId'] == city_id]
            print(f"   After City filter ({city.title()}): {len(results)} properties")
        else:
            print(f"     City '{city}' not found in database, skipping city filter")
   
    if 'max_price_cr' in filters:
        max_price = filters['max_price_cr']
        results = results[results['price_cr'] <= max_price]
        print(f"   After Max Price filter (≤ ₹{max_price} Cr): {len(results)} properties")
    
    if 'min_price_cr' in filters:
        min_price = filters['min_price_cr']
        results = results[results['price_cr'] >= min_price]
        print(f"   After Min Price filter (≥ ₹{min_price} Cr): {len(results)} properties")
    
    if 'status' in filters:
        status = filters['status']
        results = results[results['status'] == status]
        print(f"   After Status filter ({status}): {len(results)} properties")
    
    if 'furnished' in filters:
        furnished = filters['furnished']
        results = results[results['furnishedType'] == furnished]
        print(f"   After Furnished filter ({furnished}): {len(results)} properties")
    
    if 'locality' in filters:
        locality = filters['locality']
        results = results[results['landmark'].str.contains(locality, case=False, na=False)]
        print(f"   After Locality filter ({locality}): {len(results)} properties")
    
    if 'min_area' in filters:
        min_area = filters['min_area']
        results = results[results['carpetArea'] >= min_area]
        print(f"   After Min Area filter (≥ {min_area} sq.ft): {len(results)} properties")
    
    if 'bathrooms' in filters:
        bathrooms = filters['bathrooms']
        results = results[results['bathrooms'] >= int(bathrooms)]
        print(f"   After Bathrooms filter (≥ {bathrooms}): {len(results)} properties")
    
    results = sort_by_relevance(results, filters)
    
    results = results.head(max_results)
    
    print(f"\n Found {len(results)} matching properties")
    
    return results


def sort_by_relevance(df, filters):

    if len(df) == 0:
        return df
    
    
    df = df.copy()
    df['relevance_score'] = 0
    
    if 'bhk' in filters:
        bhk = filters['bhk']
        df.loc[df['type'].str.contains(f'{bhk}BHK', case=False, na=False), 'relevance_score'] += 100
    
    if 'max_price_cr' in filters:
        max_price = filters['max_price_cr']
        df['price_diff'] = max_price - df['price_cr']
        df.loc[df['price_diff'] >= 0, 'relevance_score'] += (50 * (1 - df['price_diff'] / max_price))
    
   
    df.loc[df['status'] == 'READY_TO_MOVE', 'relevance_score'] += 20
    

    if df['carpetArea'].max() > 0:
        df['relevance_score'] += (df['carpetArea'] / df['carpetArea'].max()) * 10
    

    df = df.sort_values('relevance_score', ascending=False)
    
    return df


def get_search_statistics(df, filters):
    
    if len(df) == 0:
        return {
            'total_count': 0,
            'avg_price_cr': 0,
            'min_price_cr': 0,
            'max_price_cr': 0,
            'localities': [],
            'status_distribution': {},
            'bhk_types': []
        }
    
    stats = {
        'total_count': len(df),
        'avg_price_cr': df['price_cr'].mean(),
        'min_price_cr': df['price_cr'].min(),
        'max_price_cr': df['price_cr'].max(),
        'avg_area': df['carpetArea'].mean(),
        'localities': df['landmark'].unique()[:5].tolist(),  # Top 5 localities
        'status_distribution': df['status'].value_counts().to_dict(),
        'bhk_types': df['type'].unique().tolist(),
        'avg_bathrooms': df['bathrooms'].mean(),
        'furnished_distribution': df['furnishedType'].value_counts().to_dict()
    }
    
    return stats


def expand_search_if_needed(df, original_filters, all_data):
    
    
    if len(df) >= 3:
        return df, None  # Enough results, no need to expand
    
    print("\n  Too few results, expanding search...")
    
    expanded_filters = original_filters.copy()
    expansion_steps = []
   
    if 'locality' in expanded_filters:
        del expanded_filters['locality']
        expansion_steps.append("removed locality filter")
    
    if 'max_price_cr' in expanded_filters:
        original_price = expanded_filters['max_price_cr']
        expanded_filters['max_price_cr'] = original_price * 1.2
        expansion_steps.append(f"increased budget to ₹{expanded_filters['max_price_cr']:.2f} Cr")
    
    if 'furnished' in expanded_filters:
        del expanded_filters['furnished']
        expansion_steps.append("included all furnishing types")
    
    expanded_results = search_properties(all_data, expanded_filters, max_results=10)
    
    if len(expanded_results) > len(df):
        expansion_message = f"Expanded search by: {', '.join(expansion_steps)}"
        return expanded_results, expansion_message
    
    return df, None


def format_property_card(row):
    return {
        'title': row['display_name'],
        'project_name': row['projectName'],
        'bhk': row['type'],
        'price_cr': row['price_cr'],
        'price_lakhs': row['price_lakhs'],
        'price_display': f"₹{row['price_cr']:.2f} Cr" if row['price_cr'] >= 1 else f"₹{row['price_lakhs']:.0f} Lakhs",
        'carpet_area': row['carpetArea'],
        'locality': row['landmark'],
        'status': row['status'],
        'status_display': 'Ready to Move' if row['status'] == 'READY_TO_MOVE' else 'Under Construction',
        'furnished': row['furnishedType'],
        'bathrooms': row['bathrooms'],
        'balcony': row.get('balcony', 'N/A'),
        'lift': 'Yes' if row.get('lift') == 'true' else 'No',
        'slug': row['slug'],
        'url': f"/project/{row['slug']}"
    }


def get_property_cards(df, max_cards=10):
    cards = []
    for idx, row in df.head(max_cards).iterrows():
        cards.append(format_property_card(row))
    
    return cards

if __name__ == "__main__":
   
    from data_loader import load_and_merge_data
    
    print("\n Loading data...")
    df = load_and_merge_data()
   
    print("\n" + "=" * 80)
    print("TEST CASE 1: 3BHK in Pune under 1.5 Cr")
    print("=" * 80)
    
    filters1 = {
        'bhk': '3',
        'city': 'pune',
        'max_price_cr': 1.5
    }
    
    results1 = search_properties(df, filters1)
    
    if len(results1) > 0:
        print("\n Search Statistics:")
        stats1 = get_search_statistics(results1, filters1)
        print(f"   Total: {stats1['total_count']} properties")
        print(f"   Avg Price: ₹{stats1['avg_price_cr']:.2f} Cr")
        print(f"   Price Range: ₹{stats1['min_price_cr']:.2f} - ₹{stats1['max_price_cr']:.2f} Cr")
        print(f"   Localities: {', '.join(stats1['localities'][:3])}")
        
        print("\n Top 3 Properties:")
        cards1 = get_property_cards(results1, max_cards=3)
        for i, card in enumerate(cards1, 1):
            print(f"\n   {i}. {card['title']}")
            print(f"       {card['locality']}")
            print(f"       {card['price_display']}")
            print(f"       {card['carpet_area']:.0f} sq.ft")
            print(f"       {card['status_display']}")
    
    print("\n\n" + "=" * 80)
    print("TEST CASE 2: Ready to move 2BHK in Mumbai")
    print("=" * 80)
    
    filters2 = {
        'bhk': '2',
        'city': 'mumbai',
        'status': 'READY_TO_MOVE'
    }
    
    results2 = search_properties(df, filters2)
    
    if len(results2) > 0:
        stats2 = get_search_statistics(results2, filters2)
        print(f"\n Found {stats2['total_count']} properties")
        print(f"   Avg Price: ₹{stats2['avg_price_cr']:.2f} Cr")
    else:
        print("\nNo results found")
        print("   Trying expanded search...")
        results2, message = expand_search_if_needed(results2, filters2, df)
        if message:
            print(f"   {message}")
            print(f"   Found {len(results2)} properties after expansion")
    
    print("\n\n" + "=" * 80)
    print("TEST CASE 3: Properties between 1-2 Crore")
    print("=" * 80)
    
    filters3 = {
        'min_price_cr': 1.0,
        'max_price_cr': 2.0
    }
    
    results3 = search_properties(df, filters3)
    stats3 = get_search_statistics(results3, filters3)
    
    print(f"\nFound {stats3['total_count']} properties")
    print(f"   BHK Types: {', '.join(stats3['bhk_types'][:5])}")
    print(f"   Status: {stats3['status_distribution']}")
    
    print("\n" + "=" * 80)
    print("Search Engine Complete")