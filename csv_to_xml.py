"""
Converts CSV files with research output metadata into XML files prepared for bulk upload in Pure Research Information Management System.
Compatible with Pure version 5.19.3.

INPUTS:
- CSV file, with headers either matching template (choose 'd') or Zotero export format ('z').

STEPS:
1. Set the source file.
2. Set the destination file.
3. Confirm the Internal Persons file (against which authors will be matched).
4. Confirm the Managing Unit to be applied to all records.
5. Confirm the Organization Name to be applied to all records.
6. Optionally: Change the default fuzzy matching ratio.
7. Optionally: Output validation tools.
8. Run the program.

OUTPUTS:
- XML file
- Optional validation tools (when detailed_output=True):
--- external_persons.txt, a list of authors from CSV file with no match in the Internal Persons file
--- group_authors.txt, a list of authors with irregular formatting, listed as groupAuthors in XML
--- internal_person_matches.txt, a list of authors from CSV with their Internal Person match(es)

REQUIREMENTS:
- fuzzywuzzy package
- python-Levenshtein package
- Microsoft Visual C++ tools
"""
import csv
import numpy as np
import pandas as pd
import re
from fuzzywuzzy import fuzz
import random


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
        # Make headers str.lower
        headers = [header.strip().lower() for header in headers]
        # Save dictionary of header:value for each row of data
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
    See Zotero-Experts-crosswalk.csv for data mapping.

    :param csv_file: A string pointing to the actual file
    :return: A list of dictionaries, where each row of data is a dictionary containing header:value pairs
    """
    df = pd.read_csv(csv_file, usecols=['Key','Item Type','Publication Year','Author', 'Title', 'Publication Title', 'ISBN',
                                        'ISSN', 'DOI', 'Url', 'Abstract Note', 'Date', 'Pages', 'Num Pages', 'Issue', 'Volume',
                                        'Series', 'Series Number', 'Publisher', 'Place', 'Rights', 'Notes', 'Manual Tags',
                                        'Automatic Tags', 'Editor', 'Edition'],
                     dtype={'Publication Year': 'Int64','Num Pages':'Int64','Volume':'object'}, encoding='utf-8')
    columns_mapper = {'Key': 'id', 'Item Type': 'type', 'Author': 'creator', 'Publication Title': 'journal',
                      'Abstract Note': 'abstract', 'Series': 'relation', 'Place': 'place of publication',
                      'Pages': 'Pages Range', 'Num Pages':'pages'}
    df = df.rename(columns=columns_mapper)
    df = df.replace(np.nan, "", regex=True)
    df['subject'] = df['Manual Tags'] + "\n" + df['Automatic Tags']
    df['notes'] = df['Notes'].astype(str) + "\n" + df['Rights'].astype(str)
    df = df.drop(columns=['Notes', 'Rights', 'Manual Tags', 'Automatic Tags'])
    df.columns = df.columns.str.lower()
    allrows = df.to_dict(orient='records')
    return allrows


def reformat_author(research_id, authors: str) -> tuple:
    """
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


def validate_internal_authors(author_list: list, internal_persons: str, custom_ratio: int) -> tuple:
    """
    Read in list of 1+ reformatted authors (scope: 1 research output) and Internal Persons file.
    For each author in author_list,
        Use fuzzy matching to compare author with all persons in Internal Persons.
        Where a match is found, grab PureID and first Unit Affiliation; else, generate random ID and unit = np.nan.
    Add each author consecutively to new validated_authors list.

    NOTE: Beware of false matches where author names are very similar but represent different people. Set detailed_output=True for report.

    :param author_list: A list of tuples with 1+ authors [('First','Last')]
    :param internal_persons: Str reference to Pure - Internal Persons file against which to validate the list of authors in csv_data.
    :param custom_ratio: 79 by default. Increase for a more strict matching test. Decrease to match more broadly.
    :return: validated_authors as [[auth_id, (First, Last)]], external_authors as set(), matches_log as list()

    >>> validate_internal_authors([('Gabrielle G.', 'Delacour'), ('Anthony', 'Goldstein')], "sample_internal_persons.xlsx") #doctest: +ELLIPSIS
     ([[403788, ('Gabrielle G.', 'Delacour'), 'Beauxbatons'], ['imported_person_...', ('Anthony', 'Goldstein'), nan]], {('Anthony', 'Goldstein')}, [('Delacour, Gabrielle G.', [('Delacour, Gabrielle', 93)])])
    >>> validate_internal_authors([('Harry', 'Potter')], "sample_internal_persons.xlsx")
    ([[345262, ('Harry', 'Potter'), 'Ilvermorny ']], set(), [('Potter, Harry', [('Potter, Larry', 92), ('Potter, Gary', 88)])])
    >>> validate_internal_authors([('Angelina', 'Johnson')], "sample_internal_persons.xlsx")
    ([[861581, ('Angelina', 'Johnson'), 'Hogwarts']], set(), [('Johnson, Angelina', [('Johnson, Angela', 94)])])
    """
    matches_log = []
    validated_authors = []
    # Create DataFrame; read in last name, first name, Pure ID
    df = pd.read_excel(internal_persons, sheet_name="Persons (0)_1",
                       usecols=["2 Last, first name", "3 Name > Last name", "4 Name > First name", "18 ID", "7.1 Organizations > Organizational unit[1]"], encoding='utf-8')
    columns_mapper = {'7.1 Organizations > Organizational unit[1]': 'unit'}
    df = df.rename(columns=columns_mapper)
    external_authors = set()
    strings_to_check = df["2 Last, first name"].to_list()
    for author in author_list:
        correct_string = str(author[1] + ", " + author[0])
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
            select_row = df.loc[df["2 Last, first name"] == ratios[0][0]]
            auth_id = select_row["18 ID"].item()
            auth_id = int(auth_id)
            unit_affiliation = select_row['unit'].item()
            matches_log.append((correct_string, ratios))
        elif len(ratios) == 0:
            # Author not found in Internal Persons file - assign random ID
            auth_id = "imported_person_" + str(random.randrange(0, 1000000)) + str(random.randrange(0, 1000000))
            unit_affiliation = np.nan
            external_authors.add(author)
        else:
            # If more than 1 person from Internal Persons file matched, return highest match
            ratios.sort(key=lambda x: x[1], reverse=True)
            matches_log.append((correct_string, ratios))
            # Use position within list to get back to the string, look up string in df to return ID using .loc
            select_row = df.loc[df["2 Last, first name"] == ratios[0][0]]
            auth_id = select_row["18 ID"].item()
            auth_id = int(auth_id)
            unit_affiliation = select_row['unit'].item()
        validated_authors.append([auth_id, author, unit_affiliation])
    return validated_authors, external_authors, matches_log


def write_author(author_list: list) -> str:
    """
    Given authors and ID, insert into XML snippet, and return XML snippet.

    :param author_list: A list of lists: ID in position 0, tuple with 1+ authors in position 1 [[ID, ('First','Last')]]
    :return: XML snippet for authors

    >>> write_author([[123, ('Angelina', 'Johnson'), 'Hogwarts'], [456, ('Gabrielle G.', 'Delacour'), 'Beauxbatons'], [789, ('Anthony', 'Goldstein'), np.nan]])     #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    <v1:author>
    ...
    </v1:author>
    """
    authors_xml_snippet = ""
    n = 0
    for author in author_list:
        authors_xml_snippet += """<v1:author>
            <v1:role>author</v1:role>
            <v1:person id='""" + str(author[0]) + """'>
                <v1:firstName>""" + str(author[1][0]) + """</v1:firstName>
                <v1:lastName>""" + str(author[1][1]) + """</v1:lastName>
            </v1:person>"""
        if author[2] is not np.nan:
            authors_xml_snippet += """
             <v1:organisations>
                    <v1:organisation>
                        <v1:name>
                            <v3:text>""" + author[2] + """</v3:text>
                        </v1:name>
                    </v1:organisation>
                </v1:organisations>"""
        authors_xml_snippet += """
        </v1:author>
        """
        n += 1
    return authors_xml_snippet


def write_editor(editor_list: list) -> str:
    """
    Given a list of editors, insert into XML snippet, and return XML snippet
    :param editor_list: A list of 1+ editors structured as [('First','Last'),('First','Last')]
    :return: XML snippet for editors

    >>> write_editor([('Bertha B.', 'Jorkins')])   #doctest: +NORMALIZE_WHITESPACE
    '<v1:editors>
        <v1:editor>
        <v3:firstname>Bertha B.</v3:firstname>
        <v3:lastname>Jorkins</v3:lastname>
        </v1:editor>
    </v1:editors>'
    >>> write_editor([('Angelina', 'Johnson'), ('Gabrielle G.', 'Delacour'), ('Anthony', 'Goldstein')])   #doctest: +ELLIPSIS   +NORMALIZE_WHITESPACE
    '<v1:editors>\n        <v1:editor>\n        <v3:firstname>Angelina</v3:firstname>\n        <v3:lastname>Johnson</v3:lastname>\n        </v1:editor>\n        <v1:editor>\n        <v3:firstname>Gabrielle G.</v3:firstname>\n        <v3:lastname>Delacour</v3:lastname>\n        </v1:editor>\n        <v1:editor>\n        <v3:firstname>Anthony</v3:firstname>\n        <v3:lastname>Goldstein</v3:lastname>\n        </v1:editor>\n    </v1:editors>'
    """

    editors_xml_snippet = "<v1:editors>"
    n = 0
    for editor in editor_list:
        editors_xml_snippet += """
        <v1:editor>
        <v3:firstname>""" + editor[0] + """</v3:firstname>
        <v3:lastname>""" + editor[1] + """</v3:lastname>
        </v1:editor>"""
    editors_xml_snippet += """
    </v1:editors>"""
    return editors_xml_snippet


def write_group_author(group_authors: str) -> str:
    """
    Given a string with a variable length of group author, insert into XML snippet, and return XML snippet
    NOTE: Group author does not require a primary key/unique ID

    :param group_authors: A string containing 1+ group authors, with multiple authors separated by || double pipes
    :return: XML snippet with group authors

    >>> write_group_author("Beauxbatons||Durmstrang")   #doctest: +NORMALIZE_WHITESPACE
    '<v1:author>
        <v1:role>author</v1:role>
        <v1:groupAuthor>Beauxbatons</v1:groupAuthor>
    </v1:author>
    <v1:author>
        <v1:role>author</v1:role>
        <v1:groupAuthor>Durmstrang</v1:groupAuthor>
    </v1:author>'
    >>> write_group_author("Hogwarts School")
    '<v1:author>\n            <v1:role>author</v1:role>\n            <v1:groupAuthor>Hogwarts School</v1:groupAuthor>\n        </v1:author>\n        '
    """
    if "||" in group_authors:
        groups = group_authors.split("||")
    else:
        groups = [group_authors]
    group_authors_xml_snippet = ""
    if group_authors != "":
        for one_group_author in groups:
            group_authors_xml_snippet += """<v1:author>
            <v1:role>author</v1:role>
            <v1:groupAuthor>""" + one_group_author + """</v1:groupAuthor>
        </v1:author>
        """
    return group_authors_xml_snippet


def write_keywords(all_keywords: str) -> str:
    """
    Given a string with a variable length of subject keywords, insert into XML snippet, and return XML snippet

    :param all_keywords: A string containing 1+ subject keywords separated by || double pipes
    :return: An XML snippet for subject keywords

    >>> write_keywords("Divination -- Crystal balls||Divination -- Tea leaves||Divination -- Palmistry")    #doctest: +NORMALIZE_WHITESPACE
    </v3:freeKeyword>
    <v3:freeKeyword>
        <v3:text>Divination -- Tea leaves</v3:text>
    </v3:freeKeyword>
    <v3:freeKeyword>
        <v3:text>Divination -- Palmistry</v3:text>
    </v3:freeKeyword>'
    """
    # Handle list of keywords separated by ; rather than ||
    if ";" in all_keywords and "||" not in all_keywords:
        all_keywords = re.sub(";", "||", all_keywords)

    keywords = all_keywords.split("||")
    keywords_xml_snippet = ""
    if all_keywords != "":
        for keyword in keywords:
            keywords_xml_snippet += """<v3:freeKeyword>
    <v3:text>""" + keyword.strip() + """</v3:text>
    </v3:freeKeyword>"""
    return keywords_xml_snippet


def write_series(all_series: str, number: int, issn: str) -> str:
    """
    Write series information to XML snippet.

    :param all_series: A string containing 1+ series separated by || double pipes. Series number information, if provided, is separated by ; colon.
    :param number: An int or np.nan containing series number.
    :param issn: A string or np.nan containing series issn.
    :return: XML snippet containing series information.

    >>> write_series("Animal Transfiguration Report Series; T-054||Hogwarts School Reports;00-11", np.nan, np.nan)
    '<v1:serie>\n    <v1:name><![CDATA[Animal Transfiguration Report Series]]></v1:name>\n    <v1:number>T-054</v1:number>\n</v1:serie>\n            <v1:serie>\n    <v1:name><![CDATA[Hogwarts School Reports]]></v1:name>\n    <v1:number>00-11</v1:number>\n</v1:serie>\n            '
    >>> write_series("Potion Brewing Manual",15,np.nan)
     '<v1:serie>\n            <v1:name><![CDATA[Potion Brewing Manual]]></v1:name>\n            <v1:number>15</v1:number>\n            \n            </v1:serie>'
    >>> write_series("Survey of Herbology Manual",np.nan,"12345678") #doctest: +NORMALIZE_WHITESPACE
     '<v1:serie>\n            <v1:name><![CDATA[Survey of Herbology Manual]]></v1:name><v1:printIssns>\n        <v1:issn>12345678</v1:issn>\n        </v1:printIssns>\n            </v1:serie>'
    """
    if "||" in all_series:
        series = all_series.split("||")  # Series is a list of serie
    else:
        series = [all_series]

    # Set nans where fields are blank
    if number == "":
        number = np.nan
    if issn == "":
        issn = np.nan

    series_xml_snippet = ""
    if number is np.nan and issn is np.nan:
        for one_serie in series:
            if ";" in one_serie:
                split_serie = one_serie.split(";")
                serie_name = split_serie[0]
                serie_number = split_serie[1]
            else:
                serie_name = str(one_serie)
                serie_number = ""
            series_xml_snippet += """<v1:serie>
        <v1:name><![CDATA[""" + serie_name.strip() + """]]></v1:name>
        <v1:number>""" + serie_number.strip() + """</v1:number>
    </v1:serie>
            """
    else:
        for one_serie in series:
            series_xml_snippet += """<v1:serie>
            <v1:name><![CDATA[""" + one_serie.strip() + """]]></v1:name>"""
            if number is not np.nan:
                series_xml_snippet += """
            <v1:number>""" + str(number).strip() + """</v1:number>
            """
            if issn is not np.nan:
                series_xml_snippet += write_barcodes(issn, 'issn')
            series_xml_snippet += """
            </v1:serie>"""
    return series_xml_snippet


def write_barcodes(all_barcodes: str, barcode_type: str) -> str:
    """
    Given a string with a variable number of barcordes, insert into XML snippet and return XML snippet.

    :param all_barcodes: A string containing 1+ ISSN barcode numbers, separated by ", " or ISBN barcodes, separated by " "
    :param barcode_type: String denoting ISSN, ISBN, etc.
    :return: An XML snippet for ISSN keywords

    >>> write_barcodes("0309-166X, 1464-3545",'issn') #doctest: +NORMALIZE_WHITESPACE
    '<v1:printIssns>
        <v1:Issn>0309-166X</v1:Issn>
        <v1:Issn>1464-3545</v1:Issn>
    </v1:printIssns>'
    >>> write_barcodes("1234-123X", 'issn') #doctest: +NORMALIZE_WHITESPACE
     '<v1:printIssns>
        <v1:Issn>1234-123X</v1:Issn>
     </v1:printIssns>'
    >>> write_barcodes("978-1-60566-264-0 978-1-60566-265-7", 'isbn') #doctest: +NORMALIZE_WHITESPACE
    '<v1:printIsbns>
        <v1:Isbn>978-1-60566-264-0</v1:Isbn>
        <v1:Isbn>978-1-60566-265-7</v1:Isbn>
    </v1:printIsbns>'
    """
    barcodes = []
    formatted_bct = barcode_type[0].upper() + barcode_type[1:].lower()
    barcode_xml_snippet = "<v1:print" + formatted_bct + "s>"
    if barcode_type == 'issn':
        barcodes = all_barcodes.split(",")
    elif barcode_type == 'isbn':
        barcodes = all_barcodes.split(" ")
    else:
        raise ValueError("Barcode type not found.")
    for barcode in barcodes:
        barcode_xml_snippet += """
        <v1:""" + formatted_bct.lower() + """>""" + barcode.strip() + """</v1:""" + formatted_bct.lower() + """>
        """
    barcode_xml_snippet += """</v1:print""" + formatted_bct + """s>"""
    return barcode_xml_snippet


def set_research_output_type(research_id, type_value: str) -> dict:
    """
    Determine research output type for 1 research output.

    :param research_id: ID of research output
    :param type_value: Contents of type column
    :return: Dictionary w/ type and subtype e.g. {'type':'book','subType':'technical_report'}
    """
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
        print("Presentation research output type not yet supported. Manually enter this data. Check rows with IDs: {}\n".format(research_id))
    else:
        print("Error in technical report type. XML validation will fail. Check rows with IDs: {}\n".format(research_id))
    return research_output_type


def write_xml(csv_data: list, internal_persons: str, managing_unit: str, organization_name: str, outfile_name: str, fuzzy_match_ratio=79, detailed_output=False):
    """
    Given csv data and the filename you want,
    Print data into an XML file, call helper functions depending on what columns are included in the data.

    :param csv_data: List of dictionaries. Each dict contains 1 research output.
    :param internal_persons: Str reference to Pure - Internal Persons file against which to validate the list of authors in csv_data.
    :param managing_unit: Value for the organizational owner can be found in Pure portal. Internal to Pure system.
    :param organization_name: Appears as the research's affiliated unit on the portal.
    :param outfile_name: The name specified for the XML outfile.
    :param fuzzy_match_ratio: Optionally, change the fuzzy match ratio.
    :param detailed_output: Bool, default False. If true, output validation tools.
    :return: None
    """
    total_research_outputs = len(csv_data)

    # Collect optional detailed output about external persons and groupAuthors, for manual review before XML import
    if detailed_output is True:
        internal_matches_outfile = open("validation_tools/internal_person_matches.txt", "w", encoding='utf-8')
        print("(Author name as listed in research publication, (Internal persons matching to author, ratio score))", file=internal_matches_outfile)
        externals_outfile = open("validation_tools/external_persons.txt", "w", encoding='utf-8')
        group_authors_outfile = open("validation_tools/group_authors.txt", "w", encoding='utf-8')
    external_persons = list()
    groups_to_print = list()
    internal_matches = list()

    # Collect all headers included in this CSV into a list for verifying contents of this specific CSV
    csv_headers = []
    for row in csv_data:
        for key in row.keys():
            key = key.lower()
            if key not in csv_headers:
                csv_headers.append(key)

    # Prepare XML outfile
    outfile = open(outfile_name, "w", encoding='utf-8')

    # Print the Pure XML namespaces above the loop through each research output.
    # NOTE: Download these namespaces from the Pure portal (Administrator > Bulk import). Link them to your XML before validating.
    print('<?xml version="1.0" encoding="utf-8"?>', file=outfile)
    print('<v1:publications xmlns:v3="v3.commons.pure.atira.dk" xmlns:v1="v1.publication-import.base-uk.pure.atira.dk">',
          file=outfile)

    # Loop through all rows in the spreadsheet.
    # Begin printing each CSV row into XML.
    counter = 0
    for row in csv_data:
        counter += 1
        # Research Output Type
        if 'type' in csv_headers:
            ro_type = set_research_output_type(row['id'], row['type'])
        else:
            ro_type = {"type": "book", "subType": "technical_report"}

        # Research Output ID
        print('<v1:'+ ro_type['type'] + ' subType="'+ ro_type['subType'] + '" id="' + row['id'] + '">', file=outfile)

        # Peer review status is hard-coded depending on the research output type.
        if ro_type['subType'] == 'article':
            print('<v1:peerReviewed>true</v1:peerReviewed>', file=outfile)
        else:
            print('<v1:peerReviewed>false</v1:peerReviewed>', file=outfile)

        # Note here that publication category and publication status are hard coded.
        print('<v1:publicationCategory>research</v1:publicationCategory>', file=outfile)
        print('<v1:publicationStatuses>', file=outfile)
        print('<v1:publicationStatus>', file=outfile)
        print('<v1:statusType>published</v1:statusType>', file=outfile)

        # Date
        print('<v1:date>', file=outfile)
        date = str(row['date'])
        if len(date) == 4:
            year = date
        else:
            year = date[:4]
            # EXPECTED DATE FORMAT: YYYY-MM-DD
            # Fix dates containing / instead of -
            if "/" in date:
                reformat = date.split("/")
                date = str(reformat[2]) + "-" + str(reformat[0]) + "-" + str(reformat[1])
        print('<v3:year>' + year + '</v3:year>', file=outfile)
        if len(date) > 4:
            full_date = date.split("-")
            month = full_date[1]
            print('<v3:month>' + month + '</v3:month>', file=outfile)
            if len(full_date) > 2:
                day = full_date[2]
                print('<v3:day>' + day + '</v3:day>', file=outfile)
        print('</v1:date>', file=outfile)

        # Publication status, workflow, language are hard coded.
        print('</v1:publicationStatus>', file=outfile)
        print('</v1:publicationStatuses>', file=outfile)
        print('<v1:workflow>approved</v1:workflow>', file=outfile)
        print('<v1:language>en_US</v1:language>', file=outfile)

        # Research output title
        print('<v1:title>', file=outfile)
        print('<v3:text lang="en" country="US"><![CDATA[' + row['title'] + ']]></v3:text>', file=outfile)
        print('</v1:title>', file=outfile)

        # # Split into title and subtitle - feature disabled
        # titles = []
        # if ":" in row['title']:
        #     titles = row['title'].split(":")
        #     print('<v3:text lang="en" country="US"><![CDATA[' + titles[0].strip() + ']]></v3:text>', file=outfile)
        # else:
        #     print('<v3:text lang="en" country="US"><![CDATA[' + row['title'] + ']]></v3:text>', file=outfile)
        # print('</v1:title>', file=outfile)
        #
        # # Research output subtitle
        # if len(titles) > 1:
        #     print('<v1:subTitle>', file=outfile)
        #     print('<v3:text lang="en" country="US"><![CDATA[' + titles[1].strip() + ']]></v3:text>', file=outfile)
        #     print('</v1:subTitle>', file=outfile)
        # elif 'subtitle' in csv_headers:
        #     if row['subtitle'] != "":
        #         print('<v1:subTitle>', file=outfile)
        #         print('<v3:text lang="en" country="US"><![CDATA[' + row['subtitle'] + ']]></v3:text>', file=outfile)
        #         print('</v1:subTitle>', file=outfile)

        # Abstract
        if row['abstract'] != "":
            print('''<v1:abstract>            
                      <v3:text lang="en" country="US"><![CDATA[''' + row['abstract'] + ''']]></v3:text>
                  </v1:abstract>''', file=outfile)

        # Persons (authors)
        print('<v1:persons>', file=outfile)
        authors, groupAuths = reformat_author(row['id'], row['creator'])
        groups_to_print.extend(groupAuths)
        if authors[0][0] != '':
            valid_author, externals, matches = validate_internal_authors(authors, internal_persons, fuzzy_match_ratio)
            print(write_author(valid_author), file=outfile)
            external_persons.extend(list(externals))
            internal_matches.extend(matches)
        # Persons (group authors, organizational authors)
        else:
            print(write_group_author(authors[0][-1]), file=outfile)
        if 'groupauthor' in csv_headers:
            print(write_group_author(row['groupauthor']), file=outfile)
        print('</v1:persons>', file=outfile)

        # Organization name
        print('<v1:organisations>', file=outfile)
        print('<v1:organisation>', file=outfile)
        print('<v1:name>', file=outfile)
        print('<v3:text>' + organization_name + '</v3:text>', file=outfile)
        print('</v1:name>', file=outfile)
        print('</v1:organisation>', file=outfile)
        print('</v1:organisations>', file=outfile)

        # Owner (Managing Unit)
        print('<v1:owner id="' + managing_unit + '"/>', file=outfile)

        # Keywords (subjects)
        if 'subject' in csv_headers:
            if row['subject'] != "":
                print('''<v1:keywords>
                    <v3:logicalGroup logicalName="keywordContainers">
                        <v3:structuredKeywords>
                            <v3:structuredKeyword>
                                <v3:freeKeywords>''', file=outfile)
                print(write_keywords(row['subject']), file=outfile)
                print('''
                                </v3:freeKeywords>
                            </v3:structuredKeyword>
                        </v3:structuredKeywords>
                    </v3:logicalGroup>
                </v1:keywords>''', file=outfile)

        # URL
        if row['url'] != "":
            print('''<v1:urls>
                  <v1:url>
                  <v1:url>''' + row['url'] + '''</v1:url>
                  <v1:type>unspecified</v1:type>
                  </v1:url>
            </v1:urls>''', file=outfile)

        # DOI
        if 'doi' in csv_headers:
            if row['doi'] != "":
                print('''<v1:electronicVersions>
                      <v1:electronicVersionDOI>
                        <v1:version>publishersversion</v1:version>
                        <v1:publicAccess>unknown</v1:publicAccess>
                        <v1:doi>''' + row['doi'] + '''</v1:doi>
                    </v1:electronicVersionDOI>
                </v1:electronicVersions>''', file=outfile)

        # NOTES
        if 'notes' in csv_headers:
            if row['notes'] != "" or row['notes'] != "\n":
                print('''<v1:bibliographicalNotes>
                    <v1:bibliographicalNote>
                        <v3:text lang="en" country="US">''' + row['notes'] + '''</v3:text>
                    </v1:bibliographicalNote>
                </v1:bibliographicalNotes>''', file=outfile)

        # IF ARTICLE SUBTYPE
        if ro_type['subType'] == 'article':
            # PAGES RANGE e.g. "10-25"
            if 'pages range' in csv_headers:
                if row['pages range'] != '':
                    print('<v1:pages>' + row['pages range'] + '</v1:pages>', file=outfile)
            # NUMBER OF PAGES
            if 'pages' in csv_headers:
                if row['pages'] != "":
                    print('<v1:numberOfPages>' + str(row['pages']) + '</v1:numberOfPages>', file=outfile)
            # JOURNAL INFO
            if 'issue' in csv_headers:
                if row['issue'] != '':
                    print('<v1:journalNumber>' + str(row['issue']) + '</v1:journalNumber>', file=outfile)
            if 'volume' in csv_headers:
                if row['volume'] != '':
                    print('<v1:journalVolume>' + row['volume'] + '</v1:journalVolume>', file=outfile)
            print('<v1:journal>', file=outfile)
            print('<v1:title>' + row['journal'] + '</v1:title>', file=outfile)
            # JOURNAL ISSN
            if 'issn' in csv_headers:
                if row['issn'] != '':
                    print(write_barcodes(row['issn'], 'issn'), file=outfile)
            print('</v1:journal>', file=outfile)

        # Books, technical reports, book chapters
        elif ro_type['type'] == 'book' or 'chapterInBook':
            # PAGES COUNT
            if 'pages' in csv_headers:
                if row['pages'] != "":
                    print('<v1:numberOfPages>' + str(row['pages']) + '</v1:numberOfPages>', file=outfile)

            # Place of Publication
            if row['place of publication'] != "":
                print('''<v1:placeOfPublication>''' + row['place of publication'] + '''</v1:placeOfPublication>''', file=outfile)

            # Book edition
            if 'edition' in csv_headers:
                if row['edition'] != '':
                    print('<v1:edition>' + row['edition'] + '</v1:edition>', file=outfile)

            # Volume
            if 'volume' in csv_headers:
                if row['volume'] != '':
                    print('<v1:volume>' + row['volume'] + '</v1:volume>', file=outfile)

            # ISBN
            if 'isbn' in csv_headers:
                if row['isbn'] != '':
                    print(write_barcodes(row['isbn'], 'isbn'), file=outfile)

            # BOOK/REPORT SERIES
            if 'relation' in csv_headers:
                if row['relation'] != "":
                    print('''<v1:series>''', file=outfile)
                    if 'series number' in csv_headers and 'issn' in csv_headers:
                        print(write_series(row['relation'], row['series number'], row['issn']), file=outfile)
                    elif 'series number' in csv_headers:
                        print(write_series(row['relation'], row['series number'], np.nan), file=outfile)
                    elif 'issn' in csv_headers:
                        print(write_series(row['relation'], np.nan, row['issn']), file=outfile)
                    else:
                        print(write_series(row['relation'], np.nan, np.nan), file=outfile)
                    print('''</v1:series>''', file=outfile)

            # HOST PUBLICATION TITLE - CH. IN BOOK - REQUIRED FIELD
            if ro_type['type'] == 'chapterInBook':
                if 'journal' in csv_headers:
                    print('<v1:hostPublicationTitle>' + row['journal'] + '</v1:hostPublicationTitle>', file=outfile)

            # PUBLISHER
            if row['publisher'] != "":
                print('''<v1:publisher>
                  <v1:name>''' + row['publisher'] + '''</v1:name>
                  </v1:publisher>''', file=outfile)

            # EDITORS
            if row['editor'] != "":
                editors, group_eds = reformat_author(row['id'], row['editor'])
                if len(editors) >= 1:
                    print(write_editor(editors), file=outfile)

            # CHAPTER IN BOOK - SERIES APPEARS BELOW EDITOR
            if ro_type['subType'] == 'chapter':
                if 'relation' in csv_headers:
                    if row['relation'] != "":
                        print('''<v1:series>''', file=outfile)
                        if 'series number' in csv_headers and 'issn' in csv_headers:
                            print(write_series(row['relation'], row['series number'], row['issn']), file=outfile)
                        elif 'series number' in csv_headers:
                            print(write_series(row['relation'], row['series number'], np.nan), file=outfile)
                        elif 'issn' in csv_headers:
                            print(write_series(row['relation'], np.nan, row['issn']), file=outfile)
                        else:
                            print(write_series(row['relation'], np.nan, np.nan), file=outfile)
                        print('''</v1:series>''', file=outfile)

        # Publication type - Closing tag
        print('</v1:' + ro_type['type'] + '>', file=outfile)

    # Print the document closing tag after completing the loop.
    print('</v1:publications>', file=outfile)
    outfile.close()

    # Print logic check to console.
    print("{} research outputs found in CSV file.\n{} research outputs saved to XML file.\n".format(total_research_outputs, counter))

    # Prepare optional validation outfiles
    if detailed_output is True:
        # print detailed output regarding internal matches
        im = set()
        for match_data in internal_matches:
            im.add((match_data[0],match_data[1][0]))
        internal_matches = list(im)
        internal_matches.sort(key=lambda x: x[1][1])
        for match in internal_matches:
            print(match, file=internal_matches_outfile)
        # print detailed output regarding external persons
        final_externals = set(external_persons)
        final_externals = list(final_externals)
        final_externals.sort(key=lambda x: x[1])
        for person in final_externals:
            print(person[0] + " " + person[1], file=externals_outfile)
        # print detailed output regarding groupAuthors
        if len(groups_to_print) >= 1:
            print("NOTE: The following authors are not correctly formatted as 'Author Last Name, First Name'. Values were converted from Author to groupAuthor. To make changes, re-run after checking rows with the following IDs.",
                  file=group_authors_outfile)
            for group in groups_to_print:
                if len(group) != 0:
                    print(group, file=group_authors_outfile)
        else:
            print("No group authors found", file=group_authors_outfile)
        # Remind re: detailed output on console
        v_tools = [("Internal person matches", "internal_person_matches.txt"),
                   ("External persons list", "external_persons.txt"),
                   ("Group authors list", "group_authors.txt")]
        for v_tool in v_tools:
            print("{} saved to: validation_tools/{}".format(v_tool[0], v_tool[1]))
        # Close outfiles
        externals_outfile.close()
        group_authors_outfile.close()
        internal_matches_outfile.close()
    return outfile


if __name__ == '__main__':
    # Set up infile and outfile names
    filename = '../path/of/your/file.csv'                                                           # Step 1
    outfile = "choose_a_name.xml"                                                                   # Step 2

    # Select file type to process
    file_type = str(input('Enter a Z for Zotero file or D for DublinCore file. '))
    if file_type.lower() in ['z', 'zotero']:
        # Load the Zotero CSV file
        print('\nNow processing: ' + filename + '...\n')
        incoming_metadata = load_zotero_csv(filename)
    elif file_type.lower() in ['d', 'dublincore', 'dublin core']:
        # Load the templated CSV file
        print('\nNow processing: ' + filename + '...\n')
        incoming_metadata = load_preformatted_csv(filename)
    else:
        raise ValueError('Invalid input.')

    # Load the names and IDs from Pure of internal Pure persons
    researchers = "../path/of/Pure_exported/excel_file.xls"                                         # Step 3
    # Enter managing unit, organization name, and URL variables
    mgr_unit = "add here"                                                                           # Step 4
    org_name = "add here"                                                                           # Step 5

    # Print the XML
    outgoing_xml = write_xml\
        (incoming_metadata, researchers, mgr_unit, org_name, outfile, detailed_output=True)     # Steps 6 and 7
    print("\nOutfile saved as: {}".format(outfile))
