"""
Converts CSV files with research output metadata into XML files prepared for bulk upload in Pure Research Information Management System.
Compatible with Pure version 5.19.3.

Requirements:
- fuzzywuzzy package
- python-Levenshtein package
- Microsoft Visual C++ tools
"""
import csv
import numpy as np
import pandas as pd
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
    Load an exported CSV from Zotero.
    See Zotero-Experts-crosswalk.csv for data mapping.

    :param csv_file: A string pointing to the actual file
    :return: A list of dictionaries, where each row of data is a dictionary containing header:value pairs
    """
    df = pd.read_csv(csv_file, usecols=['Key','Item Type','Publication Year','Author', 'Title', 'Publication Title', 'ISBN', 'ISSN', 'DOI', 'Url', 'Abstract Note', 'Date', 'Pages', 'Num Pages', 'Issue', 'Volume', 'Series', 'Series Number', 'Publisher', 'Place', 'Rights', 'Notes', 'Automatic Tags', 'Editor'],
                     dtype={'Publication Year': 'Int64','Num Pages':'Int64'}, encoding='utf-8')
    columns_mapper = {'Key': 'id', 'Item Type': 'type', 'Author': 'creator', 'Title': 'title', 'Publication Title': 'journal', 'DOI': 'doi', 'Url': 'url', 'Abstract Note': 'abstract', 'Date': 'date', 'Series': 'relation', 'Publisher': 'publisher', 'Place': 'place of publication', 'Automatic Tags': 'subject', 'Pages':'Pages Range', 'Num Pages':'pages'}
    df = df.rename(columns=columns_mapper)
    df = df.replace(np.nan, "", regex=True)
    df['notes'] = df['Notes'].astype(str) + "\n" + df['Rights'].astype(str)
    df = df.drop(columns=['Notes', 'Rights'])
    allrows = df.to_dict(orient='records')
    return allrows


def reformat_author(authors: str) -> list:
    """
    Given a string with a variable length of author names, split into first/last fields. Handle name suffixes.
    Returns an error with list of related IDs where organizations are listed instead of individuals.

    :param authors: A string containing 1+ author(s) separated by || double pipes
    :return: A list of tuples [('First', 'Last')]
    >>> reformat_author('Zabini, Blaise C.||Vance, Emmeline G.||Podmore, Sturgis D.||Crouch, Barty C., Jr.||')
    [('Blaise C.', 'Zabini'), ('Emmeline G.', 'Vance'), ('Sturgis D.', 'Podmore'), ('Barty C.', 'Crouch, Jr.')]
    >>> reformat_author('')
    ValueError: Author field is blank.
    >>> reformat_author('Johnson, Angelina; Delacour, Gabrielle G.; Goldstein, Anthony')
    [('Angelina', 'Johnson'), ('Gabrielle G.', 'Delacour'), ('Anthony', 'Goldstein')]
    >>> reformat_author('Jorkins, Bertha B.')
    [('Bertha B.', 'Jorkins')]
    """
    reformatted_authors = []
    if "||" in authors:
        authors_by_full_name = authors.split("||")
    elif ";" in authors:
        authors_by_full_name = authors.split("; ")
    elif len(authors) < 1:
        raise ValueError("Author field is blank.")
    else:
        authors_by_full_name = [authors]
    for full_author in authors_by_full_name:
        if len(full_author) < 1:
            # If the length of the full_author string is shorter than 1 character, skip to prevent blanks in a list of otherwise valid authors.
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
                author_last = split_author[0]
                author_first = ""
                print("\nNOTE: '{}' is not correctly formatted as 'Author Last Name, First Name'. XML will not validate. Check your CSV file.\n".format(split_author[0]))
            reformatted_authors.append((author_first, author_last))
    return reformatted_authors


def validate_internal_authors(author_list: list, internal_persons: str, detailed_output=False) -> list:
    """
    TODO: TEST THIS FUNCTION THOROUGHLY
    Read in list of 1+ reformatted authors (scope: 1 research output) and Internal Persons file.

    For each author in author_list,
        Use fuzzy matching to compare author with all persons in Internal Persons.
        Where a match is found, grab PureID; else, generate random ID.

    Add each author consecutively to new validated_authors list.

    :param author_list: A list of tuples with 1+ authors [('First','Last')]
    :param internal_persons: Str reference to Pure - Internal Persons file against which to validate the list of authors in csv_data.
    :param detailed_output: Bool, default False. If true, print to console when choosing between multiple matched persons.
    :return: validated_authors as [[auth_id, (First, Last)]]
    >>> validate_internal_authors([('Angelina', 'Johnson'), ('Gabrielle G.', 'Delacour'), ('Anthony', 'Goldstein')], "../ExpertsSCP/Pure persons - 11921.xls") #doctest: +ELLIPSIS
    [[..., ('Angelina', 'Johnson')], ['...', ('Gabrielle G.', 'Delacour')], ['...', ('Anthony', 'Goldstein')]]
    """
    validated_authors = []

    # Create DataFrame; read in last name, first name, Pure ID
    df = pd.read_excel(internal_persons, sheet_name="Persons (0)_1",
                       usecols=["2 Last, first name", "3 Name > Last name", "4 Name > First name", "18 ID"], encoding='utf-8')

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
                if ratio > 74:
                    ratios.append((string, ratio))
        if len(ratios) == 1:
            # Look up ratios[0] in df, return the ID of that match using .loc
            select_row = df.loc[df["2 Last, first name"] == ratios[0][0]]
            auth_id = int(select_row["18 ID"])
        elif len(ratios) == 0:
            # Author not found in Internal Persons file - assign random ID
            auth_id = "imported_person_" + str(random.randrange(0, 1000000)) + str(random.randrange(0, 1000000))
        else:
            # If more than 1 person from Internal Persons file matched, return highest match
            ratios.sort(key=lambda x: x[1], reverse=True)
            if detailed_output is True:
                print("Author name as listed in CSV file: {}".format(correct_string))
                print("Internal persons matching to author: ")
                for ratio in ratios:
                    print(ratio)
                print("Author matched to result with highest ratio number listed above.")
            # Use position within list to get back to the string, look up string in df to return ID using .loc
            select_row = df.loc[df["2 Last, first name"] == ratios[0][0]]
            auth_id = int(select_row["18 ID"])
        # TODO: Check with Mark. Upload the author name as listed in CSV, or as found in Pure? (ID will ensure they match either way).
        validated_authors.append([auth_id, author])
    return validated_authors


def write_author(author_list) -> str:
    """
    Given authors and ID, insert into XML snippet, and return XML snippet.

    :param author_list: A list of lists: ID in position 0, tuple with 1+ authors in position 1 [[ID, ('First','Last')]]
    :return: XML snippet for authors
    >>> write_author([[123, ('Angelina', 'Johnson')], [456, ('Gabrielle G.', 'Delacour')], [789, ('Anthony', 'Goldstein')]])
    """
    authors_xml_snippet = ""
    n = 0
    for author in author_list:
        authors_xml_snippet += """
        <v1:author>
            <v1:role>author</v1:role>
            <v1:person id='""" + str(author[0]) + """'>
                <v1:firstName>""" + str(author[1][0]) + """</v1:firstName>
                <v1:lastName>""" + str(author[1][1]) + """</v1:lastName>
            </v1:person>
        </v1:author>
        """
        n += 1
    return authors_xml_snippet


def write_group_author(group_authors: str) -> str:
    """
    Given a string with a variable length of group author, insert into XML snippet, and return XML snippet
    :param group_authors: A string containing 1+ group authors, with multiple authors separated by || double pipes
    :return: XML snippet with group authors
    >>> write_group_author("Illinois Institute of Technology||Illinois Waste Management and Research Center")
    '<v1:author>
        <v1:role>author</v1:role>
        <v1:groupAuthor>Illinois Institute of Technology</v1:groupAuthor>
    </v1:author>
    <v1:author>
        <v1:role>author</v1:role>
        <v1:groupAuthor>Illinois Waste Management and Research Center</v1:groupAuthor>
    </v1:author>'
    """
    groups = group_authors.split("||")
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
    >>> write_keywords("Water pollution -- Illinois||Illinois River||Metals -- Water pollution -- Illinois||Polycyclic aromatic hydrocarbons -- Water pollution -- Illinois")
    '<v3:freeKeyword>
        <v3:text>Water pollution -- Illinois</v3:text>
    </v3:freeKeyword>
    <v3:freeKeyword>
        <v3:text>Illinois River</v3:text>
    </v3:freeKeyword>
    <v3:freeKeyword>
        <v3:text>Metals -- Water pollution -- Illinois</v3:text>
    </v3:freeKeyword>
    <v3:freeKeyword>
        <v3:text>Polycyclic aromatic hydrocarbons -- Water pollution -- Illinois</v3:text>
    </v3:freeKeyword>'
    """
    keywords = all_keywords.split("||")
    keywords_xml_snippet = ""
    if all_keywords != "":
        for keyword in keywords:
            keywords_xml_snippet += """
    <v3:freeKeyword>
        <v3:text>""" + keyword + """</v3:text>
    </v3:freeKeyword>"""
    return keywords_xml_snippet


def write_series(all_series: str) -> str:
    """
    Write series information to XML snippet

    :param all_series: A string containing 1+ series separated by || double pipes. Series number information, if provided, is separated by ; colon.
    :return: XML snippet containing series information.
    >>> write_series("Hazardous Waste Research and Information Center Research Report Series; RR-054||Illinois State Geological Survey Environmental Geology; 137")
    '<v1:serie>
        <v1:name>Hazardous Waste Research and Information Center Research Report Series</v1:name>
        <v1:number>RR-054</v1:number>
    </v1:serie>
    <v1:serie>
        <v1:name>Illinois State Geological Survey Environmental Geology</v1:name>
        <v1:number>137</v1:number>
    </v1:serie>'
    """
    series_xml_snippet = ""
    series = all_series.split("||")     # Series is a list of serie
    for one_serie in series:
        if ";" in one_serie:
            split_serie = one_serie.split(";")
            serie_name = split_serie[0]
            serie_number = split_serie[1]
        else:
            serie_name = str(one_serie)
            serie_number = ""
        series_xml_snippet += """
        <v1:serie>
            <v1:name>""" + serie_name.strip() + """</v1:name>
            <v1:number>""" + serie_number.strip() + """</v1:number>
        </v1:serie>
        """
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
        <v1:""" + formatted_bct + """>""" + barcode.strip() + """</v1:""" + formatted_bct + """>
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
    """ 
    MAPPING FROM XSD 
     <xs:element name="publications">
        <xs:complexType>
            <xs:choice maxOccurs="unbounded" minOccurs="1">
                <xs:element ref="contributionToJournal" />
                <xs:element ref="chapterInBook" />
                <xs:element ref="contributionToConference" />
                <xs:element ref="contributionToSpecialist" />
                <xs:element ref="patent" />
                <xs:element ref="other" />
                <xs:element ref="book" />
                <xs:element ref="workingPaper" />
                <xs:element ref="nonTextual" />
                <xs:element ref="memorandum" />
                <xs:element ref="contributionToMemorandum" />
                <xs:element ref="thesis" />
            </xs:choice>
        </xs:complexType>
    </xs:element>
    """
    research_output_type = {}
    if 'book' in type_value.lower():
        research_output_type['type'] = 'book'
        research_output_type['subType'] = 'book'
    elif 'technical' or 'report' in type_value.lower():
        research_output_type['type'] = 'book'
        research_output_type['subType'] = 'technical_report'
    elif 'booksection' in type_value.lower():
        research_output_type['type'] = 'chapterInBook'
        research_output_type['subType'] = 'chapter'
    elif 'other' and 'conference' in type_value.lower():
        research_output_type['type'] = 'contributionToConference'
        research_output_type['subType'] = 'other'
    elif 'conference' or 'conferencepaper' or 'proceeding' in type_value.lower():
        research_output_type['type'] = 'contributionToConference'
        research_output_type['subType'] = 'paper'
    elif 'journal' or 'article' or 'journalarticle' in type_value.lower():
        research_output_type['type'] = 'contributionToJournal'
        research_output_type['subType'] = 'article'
    elif 'presentation' in type_value.lower():
        print("Presentation research output type not yet supported. Manually enter this data. Check rows with IDs: {}\n".format(research_id))
    else:
        print("Error in technical report type. XML validation will fail. Check rows with IDs: {}\n".format(research_id))
    return research_output_type


def write_xml(csv_data: list, internal_persons: str, managing_unit: str, organization_name: str, url_text: str, outfile_name: str):
    """
    Given csv data and the filename you want,
    Print data into an XML file, call helper functions depending on what columns are included in the data.

    :param csv_data: List of dictionaries. Each dict contains 1 research output.
    :param internal_persons: Str reference to Pure - Internal Persons file against which to validate the list of authors in csv_data.
    :param managing_unit: Value for the organizational owner can be found in Pure portal. Internal to Pure system.
    :param organization_name: Appears as the research's affiliated unit on the portal.
    :param url_text: Appears on portal as the description of a URL, e.g. "IDEALS Repository Link".
    :param outfile_name: The name specified for the XML outfile.
    :return: None
    """
    total_research_outputs = len(csv_data)
    # Collect all headers included in this CSV into a list for verifying contents of this specific CSV
    csv_headers = []
    for row in csv_data:
        for key in row.keys():
            if key not in csv_headers:
                csv_headers.append(key)

    # Prepare outfile
    outfile = open(outfile_name, "w", encoding='utf-8')

    # Print the Pure XML namespaces above the loop through each research output.
    # NOTE: You must download these namespaces from the Pure portal (Administrator > Bulk import). Link them to your XML before validating.
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
            print('<v1:peerReviewed>True</v1:peerReviewed>', file=outfile)
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
        if 'subtitle' in csv_headers:
            if row['subtitle'] != "":
                print('<v1:subTitle>', file=outfile)
                print('<v3:text lang="en" country="US">' + row['subtitle'] + '</v3:text>', file=outfile)
                print('</v1:subTitle>', file=outfile)
            else:
                continue

        # Abstract
        if row['abstract'] != "":
            print('''<v1:abstract>            
                      <v3:text lang="en" country="US"><![CDATA[''' + row['abstract'] + ''']]></v3:text>
                  </v1:abstract>''', file=outfile)

        # Persons (authors)
        print('<v1:persons>', file=outfile)
        authors = reformat_author(row['creator'])
        valid_author = validate_internal_authors(authors, internal_persons)
        print(write_author(valid_author), file=outfile)

        # Persons (group authors, organizational authors)
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
                print('''
                <v1:keywords>
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
                    <v3:logicalGroup logicalName="librarianKeywordContainers">
                        <v3:structuredKeywords>
                            <v3:structuredKeyword classification="/dk/atira/pure/core/keywords/A/AC"/>
                        </v3:structuredKeywords>
                    </v3:logicalGroup>
                </v1:keywords>''', file=outfile)

        # URL
        if row['url'] != "":
            print('''<v1:urls>
                  <v1:url>
                  <v1:url>''' + row['url'] + '''</v1:url>
                  <v1:description>
                  <v3:text>''' + url_text + '''</v3:text>
                  </v1:description>
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
            if 'Pages Range' in csv_headers:
                if row['Pages Range'] != '':
                    print('<v1:pages>' + row['Pages Range'] + '</v1:pages>', file=outfile)
            # NUMBER OF PAGES
            if 'pages' in csv_headers:
                if row['pages'] != "":
                    print('<v1:numberOfPages>' + row['pages'] + '</v1:numberOfPages>', file=outfile)
            # JOURNAL INFO
            if 'Issue' in csv_headers:
                if row['Issue'] != '':
                    print('<v1:journalNumber>' + row['Issue'] + '</v1:journalNumber>', file=outfile)
            if 'Volume' in csv_headers:
                if row['Volume'] != '':
                    print('<v1:journalVolume>' + row['Volume'] + '</v1:journalVolume>', file=outfile)
            print('<v1:journal>', file=outfile)
            print('<v1:title>' + row['journal'] + '</v1:title>', file=outfile)
            # JOURNAL ISSN
            if 'issn' in csv_headers:
                if row['issn'] != '':
                    print(write_barcodes(row['issn'],'issn'), file=outfile)
            print('</v1:journal>', file=outfile)

        # Books, technical reports, book chapters
        elif ro_type['type'] == 'book' or 'chapterInBook':
            # PAGES COUNT
            if 'pages' in csv_headers:
                if row['pages'] != "":
                    print('<v1:numberOfPages>' + row['pages'] + '</v1:numberOfPages>', file=outfile)

            # Place of Publication
            if row['place of publication'] != "":
                print('''<v1:placeOfPublication>''' + row['place of publication'] + '''</v1:placeOfPublication>''', file=outfile)

            # ISBN
            if 'isbn' in csv_headers:
                if row['isbn'] != '':
                    print(write_barcodes(row['isbn'],'isbn'), file=outfile)

            # SERIES - TECHNICAL REPORTS
            if ro_type['subType'] == 'technical_report':
                if 'relation' in csv_headers:
                    if row['relation'] != "":
                        print('''<v1:series>''', file=outfile)
                        print(write_series(row['relation']), file=outfile)
                        if 'issn' in csv_headers:
                            if row['issn'] != '':
                                print(write_barcodes(row['issn'], 'issn'), file=outfile)
                        print('''</v1:series>''', file=outfile)

            # HOST PUBLICATION TITLE - CH. IN BOOK
            elif ro_type['subType'] == 'chapter':
                if 'journal' in csv_headers:
                    if row['journal'] != "":
                        print('<v1:hostPublicationTitle>' + row['journal'] + '</v1:hostPublicationTitle>', file=outfile)

            # PUBLISHER
            if row['publisher'] != "":
                print('''<v1:publisher>
                  <v1:name>''' + row['publisher'] + '''</v1:name>
                  </v1:publisher>''', file=outfile)

            # EDITORS
            #     if row[17] != "":
            #         print('<v1:editors>', file=outfile)
            #         print('''<v1:editor>
            #               <v3:firstname>'''+row[18]+'''</v3:firstname>
            #               <v3:lastname>'''+row[17]+'''</v3:lastname>
            #               </v1:editor>''',file=outfile)
            #         print('</v1:editors>', file=outfile)

            if ro_type['subType'] == 'chapter':
                if 'relation' in csv_headers:
                    if row['relation'] != "":
                        print('''<v1:series>''', file=outfile)
                        print(write_series(row['relation']), file=outfile)
                        if 'issn' in csv_headers:
                            if row['issn'] != '':
                                print(write_barcodes(row['issn'], 'issn'), file=outfile)
                        print('''</v1:series>''', file=outfile)

        # Publication type - Closing tag
        print('</v1:' + ro_type['type'] + '>', file=outfile)

    # Print the document closing tag after completing the loop.
    print('</v1:publications>', file=outfile)
    outfile.close()

    # Print logic check to console.
    print("CSV contains {} research outputs.\n{} research outputs were saved to XML file.".format(total_research_outputs, counter))
    return outfile


if __name__ == '__main__':
    file_type = str(input('Enter a Z for Zotero file or D for DublinCore file. '))
    if file_type.lower() in ['z', 'zotero']:
        # Load the Zotero CSV file
        filename = '../ExpertsSCP/PRIBooks.csv'
        print('\nNow processing ' + filename + '...\n')
        incoming_metadata = load_zotero_csv(filename)
    elif file_type.lower() in ['d', 'dublincore', 'dublin core']:
        # Load the templated CSV file
        filename = "../ExpertsSCP/refactored_code/dummy_technical_report_data.csv"
        print('\nNow processing ' + filename + '...\n')
        incoming_metadata = load_preformatted_csv(filename)
    else:
        raise ValueError('Invalid input.')

    # Load the names and IDs from Pure of internal Pure persons
    researchers = "../ExpertsSCP/Pure persons - 11921.xls"

    # Enter managing unit, organization name, and URL variables
    # TODO: Allow user to input the values for these variables
    mgr_unit = "123"
    org_name = "Illinois Sustainable Technology Center"
    url = "IDEALS repository link"

    # Print the XML
    outgoing_xml = write_xml(incoming_metadata, researchers, mgr_unit, org_name, url, "PRI_test_outfile.xml")
