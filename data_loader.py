import pandas as pd
import os

def load_and_merge_data(data_folder='data'):
    try:
        projects_df = pd.read_csv(os.path.join(data_folder, 'project.csv'))
        addresses_df = pd.read_csv(os.path.join(data_folder, 'ProjectAddress.csv'))
        configs_df = pd.read_csv(os.path.join(data_folder, 'ProjectConfiguration.csv'))
        variants_df = pd.read_csv(os.path.join(data_folder, 'ProjectConfigurationVariant.csv'))
        
        print(f"Loaded {len(projects_df)} projects")
        print(f"Loaded {len(addresses_df)} addresses")
        print(f"Loaded {len(configs_df)} configurations")
        print(f"Loaded {len(variants_df)} variants")
        
    except FileNotFoundError as e:
        print(f"Error: Could not find CSV files in '{data_folder}' folder")
        raise e
    merged_df = pd.merge(
        projects_df,
        addresses_df,
        left_on='id',          
        right_on='projectId',  
        how='left',            
        suffixes=('', '_address')
    )
    merged_df = pd.merge(
        merged_df,
        configs_df,
        left_on='id',           
        right_on='projectId',   
        how='left',
        suffixes=('', '_config')
    )
    merged_df = pd.merge(
        merged_df,
        variants_df,
        left_on='id_config',
        right_on='configurationId',
        how='left',
        suffixes=('', '_variant')
    )
    merged_df = clean_data(merged_df)
    print(merged_df.columns)
    print(merged_df.dtypes)
    
    return merged_df


def clean_data(df):
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['carpetArea'] = pd.to_numeric(df['carpetArea'], errors='coerce')
    df['bathrooms'] = pd.to_numeric(df['bathrooms'], errors='coerce')
    df['price'] = df['price'].fillna(0)
    df['carpetArea'] = df['carpetArea'].fillna(0)
    df['bathrooms'] = df['bathrooms'].fillna(0)
    df['landmark'] = df['landmark'].fillna('Location not specified')
    df['type'] = df['type'].fillna('Not specified')
    
    df['price_cr'] = df['price'] / 10000000
    df['price_lakhs'] = df['price'] / 100000
    
    df['display_name'] = df['projectName'] + ' - ' + df['type']
   
    df = df[df['price'] > 0]
    
    return df


def get_city_mapping():
    """
    Maps city IDs to city names.
    
    Since the CSV uses IDs like 'cmf6nu3ru000gvcxspxarll3v',
    we need to map them to readable names like 'Mumbai', 'Pune'
    
    Returns:
        dict: Mapping of city IDs to names
    """
    city_mapping = {
        'cmf6nu3ru000gvcxspxarll3v': 'Mumbai',
        'cmf50r5a00000vcj0k1iuocuu': 'Pune',
        # Add more cities as you discover them in the data
    }
    return city_mapping


def get_city_id(city_name):
    city_mapping = get_city_mapping()
    reverse_mapping = {v.lower(): k for k, v in city_mapping.items()}
    return reverse_mapping.get(city_name.lower())


def display_sample_data(df, num_samples=3):
    print("\nSample Properties:")
    print("-" * 80)
    
    for idx, row in df.head(num_samples).iterrows():
        print(f"\n{row['display_name']}")
        print(f"Location: {row['landmark']}")
        print(f"Price: ₹{row['price_cr']:.2f} Cr (₹{row['price_lakhs']:.0f} Lakhs)")
        print(f"Carpet Area: {row['carpetArea']:.0f} sq.ft")
        print(f"Bathrooms: {row['bathrooms']:.0f}")
        print(f"Status: {row['status']}")
        print(f"Furnished: {row['furnishedType']}")


if __name__ == "__main__":
    print("Testing Data Loader...\n")
    
    df = load_and_merge_data()
    
    print("\n Data Statistics:")
    print(f" Total properties: {len(df)}")
    print(f" Average price: ₹{df['price_cr'].mean():.2f} Cr")
    print(f" Price range: ₹{df['price_cr'].min():.2f} Cr to ₹{df['price_cr'].max():.2f} Cr")
    print(f" Property types: {df['type'].unique()}")
  
    display_sample_data(df)
    
    print("\nworking correctly!")