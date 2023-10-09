from datetime import datetime
from urllib.request import urlopen
from bs4 import BeautifulSoup
import requests
import urllib.parse

no_pages = 2

filters = [
	{
        "destination": "Vung Tau, Ba Ria-Vung Tau Province, Vietnam", 
        "lat_long": "10.34589,107.076462", 
        "region_id": 6054414,
        "rooms":  1,
        "start_date": "2023-10-02",
        "end_date": "2023-10-03",
        "num_adults": 2,
        "num_child": 1,
        "sort": "RECOMMENDED"
    },
    {
        "destination": "Vung Tau, Ba Ria-Vung Tau Province, Vietnam", 
        "lat_long": "10.34589,107.076462", 
        "region_id": 6054414,
        "rooms":  1,
        "start_date": "2023-10-02",
        "end_date": "2023-10-03",
        "num_adults": 2,
        "num_child": 1,
        "sort": "RECOMMENDED"
    },
] 


def get_data(pageNo=1):  
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
        "Accept-Encoding":"gzip, deflate", 
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", 
        "DNT":"1",
        "Connection":"close", 
        "Upgrade-Insecure-Requests":"1"
    }

    for filter in filters:
        destinationUrl = urllib.parse.quote(filter["destination"])

        r = requests.get(
            url=f'''https://www.expedia.com/Hotel-Search?adults={filter["num_adults"]}&children=&destination={destinationUrl}&endDate={filter["end_date"]}&latLong={filter["lat_long"]}&mapBounds=&pwaDialog=&regionId={filter["region_id"]}&rooms={filter["rooms"]}&semdtl=&sort={filter["sort"]}&startDate={filter["start_date"]}&theme=&useRewards=false&userIntent=
            ''',
            headers=headers
            )
        content = r.content
        soup = BeautifulSoup(content, 'lxml')

        

    

get_data()

# results = []
# for i in range(1, no_pages+1):
#     get_data(i)
    # results.append(get_data(i))
# flatten = lambda l: [item for sublist in l for item in sublist]
# df = pd.DataFrame(flatten(results),columns=['Book Name','Author','Rating','Customers_Rated', 'Price'])
# df.to_csv('amazon_products.csv', index=False, encoding='utf-8')

