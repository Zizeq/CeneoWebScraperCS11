import os
import json
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from config import headers
from app.utils import extract_data, translate_data

class Product:
    def __init__(self, product_id, product_name="", opinions=[], stats={}):
        self.product_id = product_id
        self.product_name = product_name
        self.opinions = opinions
        self.stats = stats

    def __str__(self):
        return f"Product_id: {self.product_id}\nProduct_name: {self.product_name}\nOpinions: "+"\n\n".join([str(opinion) for opinion in self.opinions])+"\n"+json.dumps(self.stats, indent=4, ensure_ascii=False)+"\n"
    
    def __repr__(self):
        return f"Product(product_id={self.product_id}, product_name={self.product_name}, opinions=["+",".join(repr(opinion) for opinion in self.opinions)+f"], stats={self.stats})"

    def extract_name(self):
        response = requests.get(f"https://www.ceneo.pl/{self.product_id}#tab=reviews", headers=headers)
        if response.status_code == 200:
            page_dom = BeautifulSoup(response.text, 'html.parser')
            self.product_name = extract_data(page_dom, "h1")
            opinions_count = extract_data(page_dom, "a.product-review__link > span")
            return bool(opinions_count)
        else:
            print(f"DEBUG: Failed to fetch product page for ID {self.product_id}. Status code: {response.status_code}")
            return False

    def extract_opinions(self):
        next_page = f"https://www.ceneo.pl/{self.product_id}#tab=reviews"
        while next_page:
            response = requests.get(next_page, headers=headers)
            if response.status_code == 200:
                print(f"DEBUG: Scraping {next_page}")
                page_dom = BeautifulSoup(response.text, 'html.parser')
                opinions_on_page = page_dom.select("div.js_product-review:not(.user-post--highlight)")
                print(f"DEBUG: Found {len(opinions_on_page)} opinions on this page.")
                if not opinions_on_page and not self.opinions:
                    next_page = None
                    continue
                for opinion_tag in opinions_on_page:
                    single_opinion = Opinion()
                    single_opinion.extract(opinion_tag).translate().transform()
                    self.opinions.append(single_opinion)
                try:
                    next_page = "https://www.ceneo.pl" + extract_data(page_dom,"a.pagination__next","href")
                except TypeError:
                    next_page = None
            else:
                print(f"DEBUG: Failed to fetch opinions page {next_page}. Status code: {response.status_code}")
                next_page = None

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'product_name': self.product_name,
            'stats': self.stats
        }

    def export_info(self):
        directory = os.path.join(os.path.dirname(__file__), 'data', 'products')
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, f"{self.product_id}.json")
        with open(file_path, "w", encoding="UTF-8") as jf:
            json.dump(self.to_dict(), jf, indent=4, ensure_ascii=False)

    def export_opinions(self):
        directory = os.path.join(os.path.dirname(__file__), 'data', 'opinions')
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, f"{self.product_id}.json")
        with open(file_path, "w", encoding="UTF-8") as jf:
            json.dump([opinion.transform_to_dict() for opinion in self.opinions], jf, indent=4, ensure_ascii=False)

    def import_opinions(self):
        opinions_file_path = os.path.join(os.path.dirname(__file__), 'data', 'opinions', f"{self.product_id}.json")
        with open(opinions_file_path, "r", encoding="UTF-8") as jf:
            opinions_data = json.load(jf)
        for opinion_dict in opinions_data:
            single_opinion = Opinion()
            for key, value in opinion_dict.items():
                setattr(single_opinion, key, value)
            self.opinions.append(single_opinion)

    def import_info(self):
        info_file_path = os.path.join(os.path.dirname(__file__), 'data', 'products', f"{self.product_id}.json")
        with open(info_file_path, "r", encoding="UTF-8") as jf:
            info = json.load(jf)
        self.product_name = info['product_name']
        self.stats = info['stats']

    def analyze(self):
        if not self.opinions:
            self.stats = {
                "opinions_count": 0, "pros_count": 0, "cons_count": 0,
                "pros_cons_count": 0, "average_rate": 0.0,
                "pros": {}, "cons": {}, "recommendations": {}, "stars": {}
            }
            return

        opinions_df = pd.DataFrame.from_dict([opinion.transform_to_dict() for opinion in self.opinions])
        self.stats["opinions_count"] = opinions_df.shape[0]
        self.stats["pros_count"] = int(opinions_df.pros_pl.astype(bool).sum()) if 'pros_pl' in opinions_df.columns else 0
        self.stats["cons_count"] = int(opinions_df.cons_pl.astype(bool).sum()) if 'cons_pl' in opinions_df.columns else 0
        self.stats["pros_cons_count"] = int(opinions_df.apply(lambda o: bool(o.pros_pl) and bool(o.cons_pl), axis=1).sum()) if 'pros_pl' in opinions_df.columns and 'cons_pl' in opinions_df.columns else 0
        self.stats["average_rate"] = float(opinions_df.stars.mean()) if 'stars' in opinions_df.columns else 0.0
        self.stats["pros"] = opinions_df.pros_en.explode().value_counts().to_dict() if 'pros_en' in opinions_df.columns and not opinions_df.pros_en.empty else {}
        self.stats["cons"] = opinions_df.cons_en.explode().value_counts().to_dict() if 'cons_en' in opinions_df.columns and not opinions_df.cons_en.empty else {}
        self.stats["recommendations"] = opinions_df.recommendation.value_counts(dropna=False).reindex([False, True, np.nan], fill_value=0).to_dict() if 'recommendation' in opinions_df.columns else {}
        self.stats["stars"] = opinions_df.stars.value_counts().reindex(list(np.arange(0,5.5,0.5)), fill_value=0).to_dict() if 'stars' in opinions_df.columns else {}

class Opinion:
    selectors = {
        "opinion_id": (None, "data-entry-id"),
        "author": ("span.user-post__author-name",),
        "recommendation": ("span.user-post__author-recomendation > em",),
        "stars": ("span.user-post__score-count",),
        "content_pl": ("div.user-post__text",),
        "pros_pl": ("div.review-feature__item--positive", None, True),
        "cons_pl": ("div.review-feature__item--negative", None, True),
        "vote_yes": ("button.vote-yes","data-total-vote"),
        "vote_no": ("button.vote-no","data-total-vote"),
        "published": ("span.user-post__published > time:nth-child(1)","datetime"),
        "purchased": ("span.user-post__published > time:nth-child(2)","datetime"),
        "content_en": (),
        "pros_en": (),
        "cons_en": ()
    }

    def __init__(self, opinion_id="", author="", recommendation=False, stars=0.0, content="", pros=[], cons=[], vote_yes=0, vote_no=0, publish_date="", purchase_date=""):
        self.opinion_id = opinion_id
        self.author = author
        self.recommendation = recommendation
        self.stars = stars
        self.content_pl = content
        self.pros_pl = pros
        self.cons_pl = cons
        self.vote_yes = vote_yes
        self.vote_no = vote_no
        self.publish_date = publish_date
        self.purchase_date = purchase_date
        self.content_en = ""
        self.pros_en = []
        self.cons_en = []
    
    def __str__(self):
        return ("\n".join([f"{key}: {getattr(self, key)}" for key in self.selectors.keys()]))+f"content_en: {self.content_en}\npros_en: {self.pros_en}\ncons_en: {self.cons_en}"
    
    def __repr__(self):
        return "Opinion("+", ".join([f"{key}={str(getattr(self, key))}" for key in self.selectors.keys()])+")"
    
    def extract(self, opinion_tag):
        for key, value in self.selectors.items():
            setattr(self, key, extract_data(opinion_tag, *value))
        return self

    def translate(self):
        if self.content_pl:
            self.content_en = translate_data(self.content_pl)
        if isinstance(self.pros_pl, list):
            self.pros_en = [translate_data(pros) for pros in self.pros_pl if pros]
        if isinstance(self.cons_pl, list):
            self.cons_en = [translate_data(cons) for cons in self.cons_pl if cons]
        return self

    def transform(self):
        self.recommendation = True if self.recommendation=='Polecam' else False if self.recommendation=="Nie polecam" else None
        try:
            self.stars = float(self.stars.split("/")[0].replace(",", ".")) if isinstance(self.stars, str) else 0.0
        except (AttributeError, ValueError):
            self.stars = 0.0
        self.vote_yes = int(self.vote_yes) if self.vote_yes else 0
        self.vote_no = int(self.vote_no) if self.vote_no else 0
        return self
    
    def transform_to_dict(self):
        return {key: getattr(self, key) for key in self.selectors.keys()}