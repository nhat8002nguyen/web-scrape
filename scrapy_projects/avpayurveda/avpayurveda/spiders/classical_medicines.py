from typing import Iterable
import scrapy
from scrapy.http import Request
from urllib import parse
from scrapy_splash import SplashRequest


lua_script = """
function main(splash, args)
    local user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    splash:set_user_agent(user_agent)

    assert(splash:go(args.url))
    assert(splash:wait(1))
    return {
        html = splash:html(),
        png = splash:png(),
        har = splash:har(),
    }
end
"""


class ClassicalMedicinesSpider(scrapy.Spider):
    name = "classical_medicines"
    allowed_domains = ["www.avpayurveda.com"]

    headers = {
        'authority': 'www.avpayurveda.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'cookie': '_gid=GA1.2.1980303940.1705296951; _pk_id.1.1906=1bded99eac5473ed.1705296951.; _gcl_au=1.1.1309385729.1705296951; _fbp=fb.1.1705296951625.1079924257; _clck=dgyt1x%7C2%7Cfif%7C0%7C1475; wp_woocommerce_session_3674f37bef02181c121c758da28ea400=t_709322e623362b84fd7f460b3cd3ea%7C%7C1705469752%7C%7C1705466152%7C%7Cd8fde9755f4f48cbfe6a8e54d096e846; mtsnb_lastvisited=1705316753; mtsnb_seen_6099=6; _gid=GA1.2.1980303940.1705296951; _pk_id_1_1906=1bded99eac5473ed.1705296951.; _pk_ses_1_1906=1; _gcl_au=1.1.1309385729.1705296951; _fbp=fb.1.1705296951625.1079924257; _clck=dgyt1x%7C2%7Cfif%7C0%7C1475; _gat=1; _ga_4MW8VGVF7Y=GS1.1.1705296951.1.1.1705297250.0.0.0; _ga=GA1.1.995955338.1705296951; _ga_XM48PF51MF=GS1.2.1705296951.1.1.1705297250.0.0.0; _clsk=u6utws%7C1705297251632%7C6%7C1%7Cq.clarity.ms%2Fcollect; _ga_4MW8VGVF7Y=GS1.1.1705302725.2.0.1705302725.0.0.0; _ga=GA1.1.995955338.1705296951; _pk_ref.1.1906=%5B%22%22%2C%22%22%2C1705302725%2C%22https%3A%2F%2Fwww.upwork.com%2F%22%5D; _pk_ses.1.1906=1; _ga_XM48PF51MF=GS1.2.1705302725.2.0.1705302725.0.0.0; _clsk=96bgjr%7C1705303671057%7C2%7C1%7Cu.clarity.ms%2Fcollect; _pk_ref_1_1906=%5B%5C%5C%5C%22%5C%5C%5C%22%2C%5C%5C%5C%22%5C%5C%5C%22%2C1705296951%2C%5C%5C%5C%22https%3A%2F%2Fwww.upwork.com%2F%5C%5C%5C%22%5D; mtsnb_lastvisit_posts=%5B776%5D',
        'origin': 'https://www.avpayurveda.com',
        'referer': 'https://www.avpayurveda.com/product-category/classical-medicines/',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
        'Content-type': 'multipart/form-data; boundary={}'.format('wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T')
    }

    def start_requests(self):

        # total 11 pages
        for page in range(1, 15):
            formdata = {
                'action': 'wopb_load_more',
                'paged': page,
                'blockId': '31e766',
                'postId': 4209,
                'blockName': 'product-blocks_product-grid-1',
                'filterAttributes[queryTax]': 'product_cat',
                'filterAttributes[productTaxonomy][taxonomy]': 'product_cat',
                'filterAttributes[productTaxonomy][term_ids][]': 69,
                'builder': 'taxonomy###product_cat###classical-medicines',
                'widgetBlockId': '',
                'wpnonce': 'f2d521f3e7'
            }
            yield scrapy.Request(
                url="https://www.avpayurveda.com/?wc-ajax=wopb_load_more",
                method='POST',
                headers=self.headers,
                body=parse.urlencode(formdata),
                callback=self.parse
            )

    def parse(self, response):
        items = response.xpath(
            '//div[@class="wopb-block-item"]')

        for item in items:
            name = item.xpath(
                './/h3[@class="wopb-block-title"]/a/text()').get()
            short_description = item.xpath(
                './/div[@class="wopb-short-description"]/text()').get()

            price = item.xpath(
                './/div[@class="wopb-product-price"]//ins//text()').getall()
            if len(price) == 0:
                price = item.xpath(
                    './/div[@class="wopb-product-price"]//text()').getall()

            price = "".join(price)

            image_url = item.xpath(
                './/div[contains(@class, "wopb-block-image")]//a//img/@src').get()

            yield {
                'id': "card" + name + short_description,
                'type': "card",
                'name': name,
                'basic_description': short_description,
                'image': image_url,
                'price': price,
            }

            yield response.follow(
                url=item.xpath(
                    './/h3[@class="wopb-block-title"]/a/@href').get(),
                callback=self.parse_detail,
                meta={
                    'id': "detail" + name + short_description,
                    'type': "detail",
                    'name': name,
                    'basic_description': short_description,
                    'image': image_url,
                    'price': price,
                }
            )

    def parse_detail(self, response):

        description_uls = response.xpath(
            '//div[contains(@class, "wp-block-product-blocks-product-description")]//ul')

        if len(description_uls) > 0:
            description = self.parse_product_description(response.xpath(
                '//div[contains(@class, "wp-block-product-blocks-product-description")]'))
        else:
            description_p = response.xpath(
                '//div[contains(@class, "wp-block-product-blocks-product-description")]//p')

            description = "\n\n".join(
                ["".join(desc_p.xpath(".//text()").getall()) for desc_p in description_p])

        ingredient_title_list = response.xpath(
            '//div[@id="key-ingredients"]//div[@class="wopb-row-content"]//div[contains(@class, "key-ing-title")]//div[contains(@class, "field__content")]')
        ingredient_desc_list = response.xpath(
            '//div[@id="key-ingredients"]//div[@class="wopb-row-content"]//div[contains(@class, "key-ing-desc")]//div[contains(@class, "field__content")]')

        ingredients = []
        for i, title_tag in enumerate(ingredient_title_list):
            title = "".join(title_tag.xpath(".//text()").getall())
            ing_desc = "".join(
                ingredient_desc_list[i].xpath(".//text()").getall())
            ingredient = f"{i+1}. {title}\n{ing_desc}"
            ingredients.append(ingredient)

        total_ingredients = "\n\n".join(ingredients)

        yield SplashRequest(
            url=response.url,
            callback=self.parse_splash_response,
            endpoint='execute',
            args={
                'lua_source': lua_script,
                'url': response.url
            },
            meta={
                'id': response.meta["id"],
                'type': "detail",
                'name': response.meta["name"],
                'basic_description': response.meta["basic_description"],
                'image': response.meta["image"],
                'price': response.meta["price"],
                "product_description": description,
                "key_ingredient": total_ingredients,
            }
        )

    def parse_product_description(self, response):
        # Initialize a variable to hold the combined and organized text
        organized_text = ""

        # Extracting Product Description
        product_description = response.xpath(
            '//h2/following-sibling::ul[1]/li//text()').getall()
        organized_text += "Product Description\n"
        for description in product_description:
            organized_text += f"- {description.strip()}\n"

        organized_text += "\n"

        # Extracting Ingredients
        ingredients = response.xpath(
            '//p[strong[contains(text(),"INGREDIENTS")]]/following-sibling::ul[1]/li//text()').getall()

        if len(ingredients) > 0:
            organized_text += "INGREDIENTS\n"
            for ingredient in ingredients:
                organized_text += f"- {ingredient.strip() if ingredient is not None else ingredient}\n"

        organized_text += "\n"

        # Extracting Benefits
        benefits = response.xpath(
            '//p[strong[contains(text(),"BENEFITS")]]/following-sibling::ul[1]/li//text()').getall()
        if len(benefits) > 0:
            organized_text += "BENEFITS\n"
            for benefit in benefits:
                organized_text += f"- {benefit.strip() if benefit is not None else benefit}\n"

        organized_text += "\n"

        # Extracting Dosage
        dosage = response.xpath(
            '//strong[contains(text(), "DOSAGE")]/following-sibling::p[1]/text()').get()
        if dosage is not None:
            organized_text += "DOSAGE\n"
            organized_text += f"{dosage.strip()}\n"

        # Print the organized text for demonstration purposes (in production, you would yield this)
        return organized_text

    def parse_splash_response(self, response):
        images = response.xpath(
            '//div[contains(@class,"iconic-woothumbs-thumbnails__image")]/img/@src').getall()
        images = [
            f"{image[:str(image).rfind('-')]}{image[str(image).rfind('.'):]}" if "x" in image else image for image in images]

        images = filter(lambda img: "https" in img, images)
        images_text = "\n".join(images)

        yield {
            'id': response.meta["id"],
            'type': "detail",
            'name': response.meta["name"],
            'basic_description': response.meta["basic_description"],
            'image': response.meta["image"],
            'price': response.meta["price"],
            "product_description": response.meta["product_description"],
            "key_ingredient": response.meta["key_ingredient"],
            "sub_images": images_text
        }
