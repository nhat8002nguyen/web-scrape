from bs4 import BeautifulSoup
import requests

no_pages = 2

class Product:
    def __init__(self, image=None, name=None, author=None, rating=None, customers_rated=None, price=None) -> None:
        self.image = image
        self.name = name
        self.author = author
        self.rating = rating
        self.customers_rated = customers_rated
        self.price = price

    def __str__(self) -> str:
        return f"""
            image url: {self.image}, 
            name: {self.name}, 
            author: {self.author}, 
            rating: {self.rating}, 
            customers_rated: {self.customers_rated}, 
            price: {self.price} 
        """

def get_data(pageNo):  
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
        "Accept-Encoding":"gzip, deflate", 
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", 
        "DNT":"1",
        "Connection":"close", 
        "Upgrade-Insecure-Requests":"1"
    }

    r = requests.get(
        'https://www.amazon.com/gp/bestsellers/books/ref=zg_bs_pg_'+str(pageNo)+'?ie=UTF8&pg='+str(pageNo), 
        headers=headers
    )#, proxies=proxies)
    content = r.content
    soup = BeautifulSoup(content, 'html.parser')

    alls = []

    for d in soup.find_all("div", {"id": "gridItemRoot"}):
        product = Product()

        # get image url of product
        prdImgDiv = d.find("div", attrs={'class':"a-spacing-mini"})
        imgTag = prdImgDiv.find("img")
        # print(imgTag)
        if prdImgDiv is not None:
            product.image = imgTag["src"]
        
        prdBody = d.find("div", attrs={"class": "p13n-sc-uncoverable-faceout"})
        # get name of product
        try:
            linkNameTag = prdBody.find_all("a")[1]
            product.name = linkNameTag.find("span").find("div").text
        except AttributeError:
            product.name = None

        # get the author name of product
        try:
            authorRow = prdBody.find("div", attrs={"class": "a-size-small"})
            if authorRow.find("a") is not None:
                product.author = authorRow.find("a").find("div").text
            elif authorRow.find("span") is not None:
                product.author = authorRow.find("span").find("div").text
        except (AttributeError, IndexError):
            product.name = None

        # get the rating of product
        try:
            ratingTooltipSpan = prdBody.find("span", attrs={"class": "a-icon-alt"})
            product.rating = ratingTooltipSpan.text
        except AttributeError:
            product.name = None

        # get the customers_rated number of product
        try:
            product.customers_rated = prdBody.find(
                "div", attrs={"class": "a-icon-row"}
                ).find(
                    "span", attrs={"class": "a-size-small"}
                    ).text
        except:
            product.customers_rated = 0

        # get the price of product
        try:
            product.price = prdBody.find("span", attrs={"class": "_cDEzb_p13n-sc-price_3mJ9Z"}).text
        except:
            product.price = 0

        print(product)
        alls.append(product)

    return alls


# results = []
for i in range(1, no_pages+1):
    get_data(i)
    # results.append(get_data(i))
# flatten = lambda l: [item for sublist in l for item in sublist]
# df = pd.DataFrame(flatten(results),columns=['Book Name','Author','Rating','Customers_Rated', 'Price'])
# df.to_csv('amazon_products.csv', index=False, encoding='utf-8')

