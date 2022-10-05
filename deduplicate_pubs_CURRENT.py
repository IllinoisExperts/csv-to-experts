# only works for research output with dois (designed for journal articles)
from api_keys import production_key
from api_keys import staging_key
import process_metadata as pm
import json
import requests

# removes duplicated records based on checking duplicated dois in the csv file and matched DOIs from pure using the api
# needs to be expanded to include ISBNs and other unique IDs


def main():
    publications = pm.load_zotero_csv("/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/pri_2022_journalArticle.csv")
    pubs_for_xml = deduper(publications)
    print(len(pubs_for_xml), 'will be sent to write_xml.py')


def deduper(publications):
    duplicate_pubs = []
    unique_pri = []
    susan_dupes = []
    pubs_to_write_xml = []
    for publication in publications:
        if pm.get_doi(publication) not in unique_pri:
            unique_pri.append(publication)
        else:
            susan_dupes.append(publication)
    for publication in unique_pri:
        doi = pm.get_doi(publication)
        pure_results = search_pure(doi, production_key())
        if result_to_doi_matcher(doi, pure_results):
            duplicate_pubs.append(publication)
        else:
            pubs_to_write_xml.append(publication)
    return pubs_to_write_xml


def search_pure(doi, api_key):
    # gets the external organization name and searches pure for it. Returns a list of external organizations from Pure.
    # If connection fails, prints associated error code.
    app_json = 'application/json'
    headers = {'Accept': app_json, 'api-key': api_key, 'Content-Type': app_json}

    values = json.dumps({"size": 5, "orderings": ["rating"],"searchString": str(doi)})
    if api_key == production_key():
        url = 'https://experts.illinois.edu/ws/api/research-outputs/search'
    else:
        url = "https://illinois-staging.pure.elsevier.com/ws/api/research-outputs/search"
    pure_response = requests.post(url, headers=headers, data=values)
    if pure_response.status_code == requests.codes.ok:
        # print('request went through...')
        # print(pure_response.url)
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
