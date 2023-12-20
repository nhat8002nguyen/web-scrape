class ProductCategoryMeta():
    main_categ: str
    sub_categ1: str
    sub_categ2: str
    sub_categ3: str
    deapest_slug: str


class ProductMetaData():
    main_categ: str
    sub_categ1: str
    sub_categ2: str
    sub_categ3: str
    product_code: str
    product_number: str


class Product(ProductMetaData):
    # Category, Sub Category, Sub Sub Category, Sub Sub Sub Category, Name, Brand, Regular Price,
    # Sale Price, Description, EAN(if Available), Images, brand description, URL,
    # order number in the popularity sort,
    # first sentence in the description (it says supplier information - blue color),

    name: str
    brand: str
    regular_price: int
    sale_price: str
    description: str
    images: list[str]
    brand_description: str
    url: str
    product_number: int
    description_first_sentence: str
    variants: str

class ProductVariant():
    product_code: str
    code: str
    name: str
    ean: str
    images: list[str]


class ProductExportData():
    products: list[Product]
    products_variants: list[ProductVariant]
    start_index: int 
    end_index: int