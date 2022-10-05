import csv
import numpy as np
import pandas as pd
import re
from fuzzywuzzy import fuzz
import random
import collections


def load_preformatted_csv(csv_file: str) -> list:
    """
    Given a CSV file with headers matching template.csv, convert into a list of dicts.

    :param csv_file: A string pointing to the actual file
    :return: A list of dictionaries, where each row of data is a dictionary containing header:value pairs
    """
    allrows = []
    with open(csv_file, 'r', newline='', encoding='utf-8') as infile:
        csvin = csv.reader(infile)
        headers = next(csvin)
        headers = [header.strip().lower() for header in headers]
        for row in csvin:
            n = 0
            your_dict = {}
            for column in row:
                your_dict[headers[n]] = column
                n += 1
            allrows.append(your_dict)
    error_rows = []
    for row in allrows:
        if len(row['date']) == 0 or len(row['date']) > 10:
            error_rows.append(row['id'])
        else:
            continue
    if len(error_rows) > 0:
        print("A publication date (at minimum, a year) is required in Pure. Check rows with IDs: {}\n".format(error_rows))
    return allrows


def load_zotero_csv(csv_file: str) -> list:
    """
    Load a CSV which has been exported from Zotero.
    https://www.zotero.org/support/kb/item_types_and_fields#item_fields
    See Zotero-Experts-crosswalk.csv for data mapping.

    :param csv_file: A string pointing to the actual file
    :return: A list of dictionaries, where each row of data is a dictionary containing header:value pairs
    """
    df = pd.read_csv(csv_file, usecols=['Key','Item Type','Publication Year','Author', 'Title', 'Publication Title', 'ISBN',
                                        'ISSN', 'DOI', 'Url', 'Abstract Note', 'Date', 'Pages', 'Num Pages', 'Issue', 'Volume',
                                        'Series', 'Series Number', 'Publisher', 'Place', 'Rights', 'Notes', 'Manual Tags',
                                        'Automatic Tags', 'Editor', 'Edition', 'Extra', 'Number', 'Conference Name'],
                     dtype={'Publication Year': 'Int64','Num Pages':'Int64','Volume':'object'}, encoding='utf-8')
    columns_mapper = {'Key': 'id', 'Item Type': 'type', 'Author': 'creator', 'Publication Title': 'journal',
                      'Abstract Note': 'abstract', 'Series': 'relation', 'Place': 'place of publication',
                      'Pages': 'Pages Range', 'Num Pages':'pages'}
    df = df.rename(columns=columns_mapper)
    df['Series Number'] = df['Series Number'].mask(pd.isnull, df['Number'])
    df['journal'] = df['journal'].mask(pd.isnull, df['Conference Name'])    # TODO: Make this conditional to 'Item Type'=conferencePaper
    # df = df.replace(np.nan, "", regex=True)
    df['subject'] = df['Manual Tags'] + "\n" + df['Automatic Tags']
    df['notes'] = df['Notes'].astype(str) + "\n" + df['Extra'].astype(str) + "\n" + df['Rights'].astype(str) + "\n" + df['Conference Name'].astype(str)
    df = df.drop(columns=['Notes', 'Rights', 'Manual Tags', 'Automatic Tags'])
    df.columns = df.columns.str.lower()
    allrows = df.to_dict(orient='records')
    return allrows


def reformat_author(research_id, authors: str) -> tuple:
    """ i'd rather just use the author thing from the patents - this is doing weird things with spacing
    Given a string with a variable length of author/editor names, split into first/last fields. Handles name suffixes.
    Returns a list of research IDs where organizations are listed instead of individuals.
    Raises ValueError where author field is blank.

    :param research_id: ID of research output
    :param authors: A string containing 1+ author(s) separated by || double pipes or ; colon
    :return: A tuple of 1) list of tuples [('First', 'Last')] and 2) list of tuples [('group author', research ID)]

    >>> reformat_author(123, 'Zabini, Blaise C.||Vance, Emmeline G.||Podmore, Sturgis D.||Crouch, Barty C., Jr.||')
    ([('Blaise C.', 'Zabini'), ('Emmeline G.', 'Vance'), ('Sturgis D.', 'Podmore'), ('Barty C.', 'Crouch, Jr.')], [])
    >>> reformat_author(123, 'Johnson, Angelina; Delacour, Gabrielle G.; Goldstein, Anthony')
    ([('Angelina', 'Johnson'), ('Gabrielle G.', 'Delacour'), ('Anthony', 'Goldstein')], [])
    >>> reformat_author(123, 'Jorkins, Bertha B.')
    ([('Bertha B.', 'Jorkins')], [])
    >>> reformat_author(123, 'Hogwarts School')
    ([('', 'Hogwarts School')], [('Hogwarts School', 123)])
    >>> reformat_author(123, '')
    ValueError: Author field is blank. Fix in the CSV file before proceeding.
    """
    # Set up variables to return
    reformatted_authors = []
    groups = []
    # Separate multiple authors
    if "||" in authors:
        authors_by_full_name = authors.split("||")
    elif ";" in authors:
        authors_by_full_name = authors.split("; ")
    elif len(authors) < 1:
        group_auth_decision = str(input('An author field is blank. Substitute a group author? Enter Y or N. '))
        if group_auth_decision.lower() in ['y', 'yes']:
            group_auth = str(input('Enter group author name: '))
            authors_by_full_name = [group_auth]
        else:
            raise ValueError("Author field is blank. Fix in the CSV file before proceeding.")
    else:
        authors_by_full_name = [authors]
    # Split authors into first and last names
    for full_author in authors_by_full_name:
        if len(full_author) < 1:
            # If the length of the full_author string is shorter than 1 character, skip to prevent blanks in a list of otherwise valid authors
            continue
        else:
            split_author = full_author.split(", ")
            if len(split_author) > 2:
                # Deal with name suffixes
                author_last = split_author[0] + ", " + split_author[2]
                author_first = split_author[1]
            elif len(split_author) == 2:
                author_last = split_author[0]
                author_first = split_author[1]
            else:
                # Deal with edge case if organizations are brought in as authors instead of group authors
                author_last = full_author
                author_first = ""
                # Save groups for review in detailed output files
                groups.append((split_author[0], research_id))
            reformatted_authors.append((author_first, author_last))
    return reformatted_authors, groups


def get_author_data(publication):
    author_list = publication['creator']
    if "||" in str(author_list):
        author_list = author_list.split('||')
    else:
        author_list = author_list.split(';')
    these_authors = []
    for author in author_list:
        these_authors.append({"last_name": get_lastname(author),
                             "first_name":get_firstname(author)})
    return these_authors

def get_editor_data(publication):
    editor_list = publication['editor']
    if type(editor_list) == str:
        if "||" in str(editor_list):
            editor_list = editor_list.split('||')
        else:
            editor_list = editor_list.split(';')
        these_editors = []
        for editor in editor_list:
            these_editors.append({"last_name": get_lastname(editor),
                                 "first_name":get_firstname(editor)})
        return these_editors
    else:
        return np.nan


def get_lastname(author_name):
    author_name = author_name.split(',')
    last_name = author_name[0]
    if len(author_name) > 2:
        last_name = last_name + ',' + author_name[1]
        return last_name.strip().title()
    else:
        return last_name.strip().title()


def get_firstname(author_name):
    author_name = author_name.split(',')
    if len(author_name) > 2:
        author_first = author_name[2].strip().title()
        author_first = re.sub('\s\s+', ' ', author_first)
        return author_first.strip().title()
    elif len(author_name) == 2:
        author_first = author_name[1].strip().title()
        author_first = re.sub('\s\s+', ' ', author_first)
        return author_first.strip().title()
    else:
        author_first = np.nan
        return author_first

def access_internal_persons(ip_file: str) -> pd.DataFrame:
    """
    Create DataFrame containing internal persons; read in last name, first name, Pure ID
    :param ip_file: Str reference to Pure - Internal Persons file against which to validate the list of authors in csv_data.
    :return: DataFrame of internal_persons
    """

    df = pd.read_excel(ip_file, sheet_name="Persons (0)_1",
                       usecols=["3 Last, first name", "4 Name > Last name", "5 Name > First name", "21 ID",
                                "10.1 Organizations > Organizational unit[1]"])
    columns_mapper = {'10.1 Organizations > Organizational unit[1]': 'unit'}
    df = df.rename(columns=columns_mapper)
    return df


def get_internal_external_authors(these_authors: list, internal_persons: pd.DataFrame, custom_ratio: int) -> tuple:
    """
    Read in list of 1+ reformatted authors (scope: 1 research output) and Internal Persons file.
    For each author in author_list,
        Use fuzzy matching to compare author with all persons in Internal Persons.
        Where a match is found, grab PureID and first Unit Affiliation; else, generate random ID and unit = np.nan.
    Add each author consecutively to new validated_authors list.
    returns a dictionary containing a list of internal and external authors. use to process author data.

    NOTE: Beware of false matches where author names are very similar but represent different people. Set detailed_output=True for report.
    """
    matches_log = []
    validated_authors = []
    external_authors = []
    strings_to_check = internal_persons["3 Last, first name"].to_list()

    for this_author in these_authors:
        correct_string =str(this_author["last_name"]) + ", " + str(this_author["first_name"])
        ratios = []
        for string in strings_to_check:
            # Exact match
            if string == correct_string:
                ratios.append((string, 100))
                break
            else:
                ratio = fuzz.ratio(string, correct_string)
                if ratio > custom_ratio:
                    ratios.append((string, ratio))
        if len(ratios) == 1:
            # Look up ratios[0] in df, return the ID of that match using .loc
            select_row = internal_persons.loc[internal_persons["3 Last, first name"] == ratios[0][0]]
            # TODO: Need to handle multiple authors with same name @ UIUC
            auth_dupes = select_row.reset_index()
            idx_len = auth_dupes.index.tolist()
            if len(idx_len) > 1:
                print("Warning! More than one UIUC faculty has the same name. Selecting the first author in list. You may want to fix this manually!")
                auth_row_one = select_row.head(1)
                auth_id = auth_row_one["21 ID"].item()
                unit_affiliation = auth_row_one['unit'].item()
            else:
                auth_id = select_row["21 ID"].item()
                unit_affiliation = select_row['unit'].item()
            auth_id = int(auth_id)
            matches_log.append((correct_string, ratios))
        elif len(ratios) == 0:
            # Author not found in Internal Persons file - assign random ID
            auth_id = "imported_person_" + str(random.randrange(0, 1000000)) + str(random.randrange(0, 1000000))
            unit_affiliation = np.nan
            # external_authors.append(this_author)
        else:
            # If more than 1 person from Internal Persons file matched, return highest match
            ratios.sort(key=lambda x: x[1], reverse=True)
            matches_log.append((correct_string, ratios))
            # Use position within list to get back to the string, look up string in df to return ID using .loc
            select_row = internal_persons.loc[internal_persons["3 Last, first name"] == ratios[0][0]]
            # auth_id = select_row["21 ID"].item()
            auth_id = select_row["21 ID"].tolist()[0]
            auth_id = int(auth_id)
            # unit_affiliation = select_row['unit'].item()
            unit_affiliation = select_row['unit'].tolist()[0]
        author_dict = {"author_id": auth_id, "author": this_author, "unit_affiliation": unit_affiliation}
        validated_authors.append(author_dict)
    #
    #     if 'imported_person' in str(auth_id):
    #         pass
    #     else:
    #         author_dict = {"author_id": auth_id, "author": this_author, "unit_affiliation": unit_affiliation}
    #         validated_authors.append(author_dict)
    # results_dict = {"internal_authors": validated_authors, "external_authors": external_authors}
    #     # except TypeError:
    #     #     print(author, 'author isnt a str; it is', type(author))
    return validated_authors


def get_research_output_type(publication) -> dict:
    """
    Determine research output type for 1 research output.

    :param research_id: ID of research output
    :param type_value: Contents of type column
    :return: Dictionary w/ type and subtype e.g. {'type':'book','subType':'technical_report'}
    """
    type_value = publication["type"]
    research_output_type = {}
    if 'booksection' in type_value.lower():
        research_output_type['type'] = 'chapterInBook'
        research_output_type['subType'] = 'chapter'
    elif 'book' in type_value.lower():
        research_output_type['type'] = 'book'
        research_output_type['subType'] = 'book'
    elif 'technical' in type_value.lower() or 'report' in type_value.lower():
        research_output_type['type'] = 'book'
        research_output_type['subType'] = 'technical_report'
    elif 'other' in type_value.lower() and 'conference' in type_value.lower():
        research_output_type['type'] = 'contributionToConference'
        research_output_type['subType'] = 'other'
    elif 'conference' in type_value.lower() or 'conferencepaper' in type_value.lower() or 'proceeding' in type_value.lower():
        research_output_type['type'] = 'chapterInBook'
        research_output_type['subType'] = 'conference'
    elif 'journal' in type_value.lower() or 'article' in type_value.lower() or 'journalarticle' in type_value.lower():
        research_output_type['type'] = 'contributionToJournal'
        research_output_type['subType'] = 'article'
    elif 'presentation' in type_value.lower():
        research_output_type['type'] = "ERROR"
        research_output_type['subType'] = "ERROR"
        print("Presentation research output type not yet supported. Manually enter this data. Check rows with IDs: {}\n".format(research_id))
    else:
        research_output_type['type'] = "ERROR"
        research_output_type['subType'] = "ERROR"
        print("Error in technical report type. XML validation will fail. Check rows with IDs: {}\n".format(publication["id"]))
    return research_output_type


def get_publication_year(publication):
    year = publication["publication year"]
    if type(year) == int:
        return year
    else:
        return np.nan


def get_title(publication):
    return publication["title"]


def get_journal(publication):
    journal = publication["journal"]
    if type(journal) == str:
        return journal
    else:
        return np.nan


def get_isbn(publication):
    isbn = publication["isbn"]
    if type(isbn) == str:
        if re.match(r'^(?=(?:\D*\d){10}(?:(?:\D*\d){3})?$)[\d-]+$', isbn):
            return isbn
        else:
            return np.nan
    else:
        return isbn


def get_issn(publication):
    issn = publication["issn"]
    cleaned_issns = []
    if type(issn) == str:
        these_issns = issn.split(',')
        for this_issn in these_issns:
            cleaned_issns.append(this_issn.strip())
        return cleaned_issns
    else:
        return np.nan


def get_doi(publication):
    return publication["doi"]


def get_url(publication):
    return publication["url"]


def get_abstract(publication):
    return publication["abstract"]



def get_pages_range(publication):
    page_range = publication["pages range"]
    if type(page_range) == str:
        if re.match(r'\d+-\d+', page_range):
            return page_range
        else:
            return np.nan
    else:
        return page_range


def get_number_pages(publication):
    number_pages = publication["pages"]
    if type(number_pages) == str:
        if re.match(r'\d+', number_pages):
            return number_pages
        else:
            return np.nan
    else:
        return number_pages


def get_issue(publication):
    issue = publication["issue"]
    if type(issue) == str:
        return issue
    else:
        return np.nan


def get_volume(publication):
    vol = publication["volume"]
    if type(vol) == str:
        if bool(re.search(r'([^0-9])', vol)):
            return np.nan
        else:
            return vol
    else:
        return np.nan


def get_relation(publication):
    return publication["relation"]


def get_series_number(publication):
    return publication["series number"]


def get_publisher(publication):
    return publication["publisher"]


def get_pub_place(publication):
    return publication["place of publication"]


def get_editor(publication):
    return publication["editor"]


def get_subject(publication):
    return publication["subject"]


def get_notes(publication):
    return publication["notes"]


def get_id(publication):
    return publication["id"]


def main():
    publications = load_zotero_csv("/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/pri_2022_journalArticle.csv")
    internal_people = access_internal_persons('/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/Pure persons - 92322.xls')
    for publication in publications:
        get_isbn(publication)
        print(publication)
        # print(get_publication_year(publication))
        # print(get_research_output_type(publication))
        # print(get_title(publication))
        authors = get_author_data(publication)
        get_publication_year(publication)
        print(get_internal_external_authors(authors, internal_people, custom_ratio=79))
        print(get_editor_data(publication))







def test_vol():
    publications = load_zotero_csv("/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/pri_2022_journalArticle.csv")
    for publication in publications:
        print(get_doi(publication))

def test_issn():
    publications = load_zotero_csv(
        "/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/pri_2022_journalArticle.csv")
    for publication in publications:
        print(get_publication_year(publication))
#
if __name__ == '__main__':
    main()
