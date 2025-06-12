#!/usr/bin/python3
# Copyright 2022 Sam Steele
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests, requests_cache, sys, os, json
from datetime import datetime, date
from config import *
import csv
import dotenv
import time
from threading import Condition



from threading import Condition
import logging
import os

logging.basicConfig(level=logging.DEBUG)


class Application(object):
    def __init__(self):
        
        self.points = []
        self.posters = {}

        
    def run(self,json_file, goodreads_file):
       
        connect(TRAKT_DATABASE)

        json_data = {}

        with open(json_file) as json_file:
            json_data = json.load(json_file)
            json_file.close()
        
        goodreads = self.process_goodreads_media(goodreads_file)  
        goodreads_json,goodreads_ids = self.goodreads_to_ryot_json(goodreads)  
        self.process_ryot_media('book',json_data, goodreads_json,goodreads_ids)
        
    def process_ryot_media(self,type,json_data, goodreads,goodreads_ids ):
        unknowns = []
        for item in json_data['media']:
            print(item)
            if item['lot'] == type:
                print("book")
                book = {}
                book["Author"] = "unknown"
                book["ISBN"] = "unknown"
                book["ISBN13"] = "unknown"
                book["Number of Pages"] = 0
                title = item["source_id"]
                titlesearch = self.titlereplace(title)
                titlebits = titlesearch.split(' ')
                if "Attack of the Seawolf" in title:
                    print("found")
                if "goodreads" in item:
                    titlesearch = goodreads_ids[str(item["goodreads"])]
                    
                if titlesearch in goodreads:
                    book = goodreads[titlesearch]
                else:
                    for bitem in goodreads:
                        bitembits = self.titlereplace(bitem).split(' ')
                        if titlesearch in bitem:
                            book = goodreads[bitem]
                            break
                        #else:
                        #    ss = set(titlebits) 
                        #    fs = set(bitembits)
                        #    ssfs = ss.intersection(fs)
                        #    if len(ssfs)/len(titlebits) >= .75:
                        #        book = goodreads[bitem]
                        
                if book["Author"] == "unknown":
                    for bitem in goodreads:
                        bitembits = self.titlereplace(bitem).split(' ')
                        aitembits = (bitem + " " + self.titlereplace(goodreads[bitem]["Author"])).split(' ')
                        
                        toremovelist = ["the","a","of",'']
                        toremoveset = set(toremovelist)
                        ss = set(titlebits) -toremoveset
                        fs = set(bitembits)-toremoveset
                        afs = set(aitembits)-toremoveset
                        ssfs = ss.intersection(fs)
                        ssfspct = len(ssfs)/len(titlebits) 
                        assfs = ss.intersection(afs)
                        assfspct = len(assfs)/len(titlebits)
                        if ssfspct  >= .60:
                            book = goodreads[bitem]
                            break
                        elif assfspct >= .60:
                            book = goodreads[bitem]
                            break
                        elif ssfspct  >= .50:
                            #book = goodreads[bitem]
                            print("partial")
                            break
                        elif ssfspct  >= .3:
                            print("partial")
                            break
                        
                if book["Author"] == "unknown":
                    unknowns.append(item)
                    print("not found")
                    continue
                    
                            
                if "collections" in item and "Watchlist" in item["collections"]:
                    measurement = "watchlist"
                else:
                    measurement = "book"
                    
                try:
                    pages = int(book["Number of Pages"])
                except:
                    pages = 0
                
                bookpoint = {
                    "measurement": measurement,
                    "tags": {
                        "id": item["identifier"],
                        "source": item["source"],
                        "author": book["Author"]
                        
                    },
                    "fields": {
                        "title": item["source_id"],
                        "isbn10": book["ISBN"],
                        "isbn13":book["ISBN13"],
                        "pages": pages,
                        "goodreads": book["Book Id"] 
                        
                    }
                }
                import copy
                bTime = None
                if "seen_history" in item:
                    for history in item["seen_history"]:
                        if "ended_on" in history:
                            bTime = history["ended_on"]
                            bookpoint["time"] = bTime
                            self.points.append(bookpoint)
                            bookpoint = copy.deepcopy(bookpoint)
                
                if "reviews" in item and len(item["reviews"]) > 0 and bTime is None:
                    for history in item["reviews"]:   
                         if "review" in history and "date" in history["review"]:
                            bTime = history["review"]["date"]
                            bookpoint["time"] = bTime
                            self.points.append(bookpoint)
                            bookpoint = copy.deepcopy(bookpoint)
                else:
                    self.points.append(bookpoint)
                    bookpoint = copy.deepcopy(bookpoint)
            #if item['lot'] == type:
            
            if len(self.points) >= 500:
                write_points(self.points)
                self.points = []
        #for item in json_data['media']:
        write_points(self.points)
        self.write_unknowns(unknowns)      
    #def process_ryot_media(self,type,json_data, goodreads ):
    
    def titlereplace(self,title):
        newtitle = title.lower().replace(':','').replace('\'','').replace('#','').replace('(','').replace(")",'').replace('-','')
        newtitle = newtitle.replace("iii",'3').replace('ii','2').replace(',','').replace('.','').replace("/",'').replace("\"",'')
        return newtitle
                    
    def process_goodreads_media(self,goodreads):
        with open(goodreads, mode='r', newline='', encoding='utf-8') as csv_file:
            # Create a CSV reader object
            csv_reader = csv.DictReader(csv_file)
            
            # Read all rows from the CSV
            rows = list(csv_reader)
            
            # Convert the rows to JSON
            json_data = json.dumps(rows, indent=4)
            #print(json_data)
            # Write JSON data to a file
            #with open(json_file_path, mode='w', encoding='utf-8') as json_file:
            #    json_file.write(json_data)
                
            #print(f"CSV data has been converted to JSON and saved to {json_file_path}")
        return json_data

        good_reads_data_dict = csv_to_json(goodreads)  
    #def process_goodreads_media(self,goodreads):
    
                   
    def goodreads_to_ryot_json(self,goodreads_json):
        json_data = json.loads(goodreads_json)

        #region goodreads csv to json source
        # {
        #     "Book Id": "17167572",
        #     "Title": "The Long War (The Long Earth, #2)",
        #     "Author": "Terry Pratchett",
        #     "Author l-f": "Pratchett, Terry",
        #     "Additional Authors": "Stephen Baxter",
        #     "ISBN": "=\"006206777X\"",
        #     "ISBN13": "=\"9780062067777\"",
        #     "My Rating": "0",
        #     "Average Rating": "3.64",
        #     "Publisher": "HarperCollins Publishers",
        #     "Binding": "Hardcover",
        #     "Number of Pages": "419",
        #     "Year Published": "2013",
        #     "Original Publication Year": "2013",
        #     "Date Read": "",
        #     "Date Added": "2021/07/06",
        #     "Bookshelves": "to-read",
        #     "Bookshelves with positions": "to-read (#13)",
        #     "Exclusive Shelf": "to-read",
        #     "My Review": "",
        #     "Spoiler": "",
        #     "Private Notes": "",
        #     "Read Count": "0",
        #     "Owned Copies": "0"
        # }

    
        filtered_data = [record for record in json_data if record.get('Exclusive Shelf') == "read"]

        new_goodread_records = {}
        new_goodread_ids = {}

        for record in json_data:
            title = self.titlereplace(record["Title"])
            new_goodread_records[title] = record
            new_goodread_ids[record["Book Id"]] =title
            
            author = record["Author"]
            goodreads = record["Book Id"]
            
        return new_goodread_records,new_goodread_ids
    #def goodreads_to_ryot_json(self,goodreads_json):       
    
    def write_unknowns(self,unknowns):
        with open('unknown.json','w') as file:
            json.dump(unknowns, file, indent = 4)
        
   


if __name__ == '__main__':
    # Configure
    
    if len(sys.argv) >= 1:
        json_file= sys.argv[1]
        if not os.path.exists(json_file):
            print(f"File {json_file} does not exist")
            sys.exit(4)
            
    if len(sys.argv) >= 2:
        goodreads_file= sys.argv[2]
        if not os.path.exists(goodreads_file):
            print(f"File {goodreads_file} does not exist")
            sys.exit(4)
            
    
    app = Application()
    app.run(json_file,goodreads_file)