# -*- coding: utf-8 -*-
"""
Created on Tue Apr 24 11:31:23 2018

@author: Heng
"""
#%% import all packages 
import requests
import json
import re
import pandas as pd
from collections import OrderedDict
from urllib.parse import urlparse
from bs4 import BeautifulSoup  as BS

#%% difinie the functions

def insee_code(city):
    """ This function will return a insee code by giving the city name.
        Params
        ======
            city: give a city name in French, Attention for paris it must be paris-15 for 15 discrete
    """
    insee_url = """https://public.opendatasoft.com/api/records/1.0/search/?q="""  + city + """&rows=0&facet=insee_com&
    facet=nom_dept&facet=nom_region&facet=statut&dataset=correspondance-code-insee-code-postal&timezone=Europe%2FBerlin"""
    
    try:
        response = requests.get(insee_url)
        if response.status_code == 200:
            response_json = json.loads(response.text)
            code = response_json["facet_groups"][0]["facets"][0]["name"]
            return code[:2] + "0" + code[2:]
        else:
            print("connection error code {d}".format(response.status_code))
            exit(0)
    except requests.exceptions.Timeout as et:
        print(et)
        exit(0)

class UrlParse():
    """ UrlParse will definie a valid url by parameters """
    def __init__(self, scheme, netloc, path, params):
        """ initialization the object. 
            Params:
            ======
                scheme : should be http or https
                netloc : the location of net, ex : www.google.com
                path : the url path 
                params : a dictionnary of parameters
        """
        self.scheme, self.netloc = scheme, netloc
        self.path, self.params = path, params
        
    def get_url(self):
        """ building a url valided by parameters """
        return self.scheme + "://" + self.netloc + "/" + self.path + "?" + "&".join([key+"="+value for key, value in self.params.items()])

def build_param(projects, balcony, terrace, price_min, price_max, surface_min, surface_max, cities):
    """ This function will return a dictionary of parameters. 
        Params:
        ======
            projects : 1 for rent, 2 for buy
            balcony : 1/1, if this appart has a balcony or not
            terrace : if this appart has a terrace
            surface_min : min surface
            surface_max : max surface
            price_min : min price
            price_max : max price
            cities : a list of location
    """
    names = ["types", "projects", "balcony", "terrace", "price", "surface", "places", "qsVersion", "engine-version"]
    
    places = "[" + "|".join(["{ci:" + insee_code(city) + "}" for city in cities]) + "]" 
    price = "NaN/" + price_max if price_min == None else price_min + "/" + price_max
    surface = surface_min + "/" + "NaN" if surface_max == None else surface_min + "/" + surface_max
    
    values = ["1,2", projects, balcony, terrace, price, surface, places, "1.0", "new"]
    return OrderedDict(zip(names, values))

def scrapy_immo(url):
    """ This function will return all information about appartements """
    
    header = {"User-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"}
    my_session = requests.Session()
    try:
        response = my_session.get(url, headers = header)
    except:
        print("connection error")
        exit(0)
        
    html_response = BS(response.text, "lxml")
        
    list_info = []
    for count, child in enumerate(html_response.find_all("div", {"class":"c-pa-criterion"})):
        list_info.append([ele.text for ele in child.find_all("em")])
        
    pieces, surface, pattern_surface = [], [], re.compile(u"m", re.I)
    for ele in list_info:
        pieces.append(ele[0])
        if bool(re.search(pattern_surface, ele[1])) == True:
            surface.append(ele[1])
        else:
            surface.append(ele[2])
        
    rents = [ele.text.replace(" ", "") for ele in html_response.find_all("span", {"class":"c-pa-cprice"})]
    locations = [ele.text for ele in html_response.find_all("div", {"class":"c-pa-city"})]
    agancy = [ele.find("div")["alt"] if ele.find("div") != None else ele.text for ele in html_response.find_all("div", {"class":"c-pa-agency"})]
    contact = [ele.find_all("a")[-1]["data-tooltip-focus"] for ele in html_response.find_all("div", {"class":"c-pa-actions"})]
    detail_link = [ele["href"] for ele in html_response.find_all("a", {"class":"c-pa-link link_AB"})]
    id_appartement = [urlparse(link).path.split("/")[-1].split(".")[0] for link in detail_link]
                
    descrptions, honoraires, garanties, charges = detail_info(id_appartement, my_session)
    
    df = pd.DataFrame({"id":id_appartement, "pieces":pieces, "surface":surface, "rents":rents, "locations":locations, "agancy":agancy, "contact":contact, 
                       "link":detail_link, "descrptions":descrptions, "charges":charges, "garanties":garanties, "honoraires":honoraires})
    return df

def detail_info(ids, session):
    """ This functino will return the description, charge, garantie and honoraires for a list if appartement given"""
    
    description, honoraires, garanties, charges = [], [], [], []
    header = {"User-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"}
    for id_ in ids:
        detail_url =  "http://www.seloger.com/detail,json,caracteristique_bien.json?idannonce=" + id_
        detail_response = session.get(detail_url, headers = header)
        detail_json = json.loads(detail_response.text)
        description.append(detail_json["descriptif"])
        
        if 'honoraires_locataires' in detail_json['infos_acquereur']['prix'].keys(): # take honoraires
            honoraire = detail_json['infos_acquereur']['prix']["honoraires_locataires"]
            if 'honoraires_edl' in detail_json['infos_acquereur']['prix'].keys():
                honoraire += detail_json['infos_acquereur']['prix']["honoraires_edl"]
            else:
                honoraire += 0
        else:
            honoraire = 0
        
        if 'garantie' in detail_json['infos_acquereur']['prix'].keys(): # take garantie
            garantie = detail_json['infos_acquereur']['prix']['garantie']
        else:
            garantie = None
            
        if 'charges_forfaitaires' in detail_json['infos_acquereur']['prix'].keys():
            charge = detail_json['infos_acquereur']['prix']['charges_forfaitaires']
        else:
            charge = None
        
        honoraires.append(honoraire)
        garanties.append(garantie)
        charges.append(charge)
        
    return description, honoraires, garanties, charges
   
#%% main function

my_params = build_param("1", "1/1", "1", None, "900", "25", None, ["vanves", "issy les moulineaux", "boulogne billancourt", "paris-15", "paris-14"])
Url = UrlParse(scheme="http", netloc="www.seloger.com", path = "list.htm", params = my_params)
my_url = Url.get_url()

df_immo = scrapy_immo(my_url)
df_immo.rents = df_immo.rents.apply(lambda x:int(x.replace("\r\n", "").replace("€", "")))
df_immo.surface = df_immo.surface.apply(lambda x:float(x.replace(" m²", "").replace(",", ".")))
df_immo["price_per_M"] = df_immo.rents / df_immo.surface
df_immo["price_one_shoot"] = df_immo.rents + df_immo.honoraires + df_immo.garanties + df_immo.charges
