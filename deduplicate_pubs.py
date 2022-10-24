# returns true if a dupe is found. False if a dupe is not found.
from api_keys import production_key
from api_keys import staging_key
import process_metadata as pm
import json
import requests
import numpy as np
# let's just make this a function to pass a single pub to 
# removes duplicated records based on checking duplicated dois in the csv file and matched DOIs from pure using the api
# needs to be expanded to include ISBNs and other unique IDs


def main():
    publications = pm.load_zotero_csv("/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/pri_import_2022_tech_reports.csv")
    for publication in publications:
        print(deduper(publication))


def deduper(publication):
    setting = pm.get_research_output_type(publication)['subType']
    if setting == 'article':
        return journal_article_deduper(publication)
    elif setting == 'book':
      return book_deduper(publication)
    else:
        print('Type', setting, 'is not supported by deduplicate_pubs.py. The record with id,', pm.get_id(publication), 'was not '
                               'checked for duplicates. Please check manually before upload.')
        return False


def journal_article_deduper(publication):
    doi = pm.get_doi(publication)
    pure_results = search_pure(doi, production_key())
    if result_to_doi_matcher(doi, pure_results):
        return True
    else:
        return False


def book_deduper(publication):
    this_isbn = pm.get_isbn(publication)
    pure_results = search_pure(this_isbn, production_key())
    if result_isbn_matcher(this_isbn, pure_results):
        return True
    else:
        return False

def search_pure(search_string, api_key):
    # gets the external organization name and searches pure for it. Returns a list of external organizations from Pure.
    # If connection fails, prints associated error code.
    app_json = 'application/json'
    headers = {'Accept': app_json, 'api-key': api_key, 'Content-Type': app_json}

    values = json.dumps({"size": 5, "orderings": ["rating"],"searchString": str(search_string)})
    if api_key == production_key():
        url = 'https://experts.illinois.edu/ws/api/research-outputs/search'
    else:
        url = "https://illinois-staging.pure.elsevier.com/ws/api/research-outputs/search"
    pure_response = requests.post(url, headers=headers, data=values)
    if pure_response.status_code == requests.codes.ok:
        pure_response_json = pure_response.json()
        # print(pure_response.json()['items'])
        try:
            # print(pure_response_json['items'][0])
            return pure_response_json['items']
        except IndexError:
            pass
    else:
        print('Trouble connecting to the Pure api. See the error code below:')
        print(pure_response.status_code)


def result_to_doi_matcher(pub_doi, result_list):
    for a_result in result_list:
        try:
            e_versions = a_result['electronicVersions']
            for e_version in e_versions:
                if e_version['doi'] == pub_doi:
                    # print({'pub_doi': pub_doi, 'matched_pub': e_version['doi']})
                    return True
                else:
                    return False
        except KeyError:
            return False


def result_isbn_matcher(isbn, result_list):
    if result_list is not None:
        for a_result in result_list:
            try:
                print_isbns = a_result['printISBNs']
                for print_isbn in print_isbns:
                    if print_isbn.replace('-', '') == isbn:
                        return True
                    else:
                        try:
                            e_isbns = a_result['electronicISBNs']
                            for e_isbn in e_isbns:
                                if e_isbn.replace('-', '') == isbn:
                                    return True
                                else:
                                    return False
                        except KeyError:
                            return False
            except KeyError:
                print('key error')
                try:
                    e_isbns = a_result['electronicISBNs']
                    for e_isbn in e_isbns:
                        if e_isbn.replace('-', '') == isbn:
                            return True
                        else:
                            return False
                except KeyError:
                    return False
    else:
        return False


def result_title_matcher(pub_title, result_list):
    for a_result in result_list:
        try:
            pure_title = a_result['title']['value'].strip().lower()
            if pure_title == pub_title.strip().lower():
                # print({'pub_title': pure_title, 'matched_pub': pure_title})
                return True
            else:
                # print({'pub_title': pure_title, 'unmatched_pub': pure_title})
                return False
        except KeyError:
            return False


if __name__ == '__main__':
    main()
