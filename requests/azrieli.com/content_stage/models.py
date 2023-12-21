class ProductCategoryMeta():
    main_categ: str
    sub_categ1: str
    sub_categ2: str
    sub_categ3: str
    deapest_slug: str


class ProductMetaData():
    main_categ: str = ""
    sub_categ1: str = ""
    sub_categ2: str = ""
    sub_categ3: str = ""
    product_code: str = ""
    product_number: str = ""

class Product(ProductMetaData):
    # Category, Sub Category, Sub Sub Category, Sub Sub Sub Category, Name, Brand, Regular Price,
    # Sale Price, Description, EAN(if Available), Images, brand description, URL,
    # order number in the popularity sort,
    # first sentence in the description (it says supplier information - blue color),

    name: str = ""
    brand: str = ""
    description: str = ""
    images: list[str] = []
    brand_description: str = ""
    url: str = ""
    product_number: int = 0
    description_first_sentence: str = ""
    attributes_values: list[(str, set[str])] = list()


    def __init__(self) -> None:
        super().__init__()

class ProductVariant(Product):
    product_code: str = ""
    type: str = "simple"
    sku: str = ""
    parent_code: str = ""
    sale_price: str = ""
    regular_price: str = ""
    image: str = ""
    attr_name1: str = ""
    attr_value1: str = ""
    attr_name2: str = ""
    attr_value2: str = "" 
    attr_name3: str = "" 
    attr_value3: str = "" 

    def __init__(self) -> None:
        super().__init__()

class ProductExportData():
    products: list[ProductVariant]
    start_index: int
    end_index: int
