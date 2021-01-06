"""
Pure research output type: Technical Report
TODO: Expand to include additional research output types
"""
import csv
import numpy as np
import pandas as pd
import random


def load_preformatted_csv(csv_file: str) -> list:
    """
    Given a CSV file, convert into a list of dicts.

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


def load_dc_data(csv_file: str) -> pd.DataFrame:
    """
    WORK IN PROGRESS to use Dublin Core exactly as exported from DSpace.
    Given the path of a csv file formatted in Dublin Core, read into a dataframe.
    Rearrange the columns to suit the needs of the XML.
    TODO: Add option to pd.cat multiple exported files? (IDEALS exports the metadata with 1 file per collection)

    :param csv_file: String of csv file for conversion
    :return: df (data frame)
    """
    # Create DataFrame; all values are objects. ID *MUST* be the first column in the file.
    df = pd.read_csv(csv_file, comment="#", header=0, index_col=0, encoding='utf-8')

    # Discard collection and coverage columns, as they have no Experts equivalent
    df = df.drop(['collection', 'coverage'], axis=1)

    # Verify that all required fields are included; if missing, fill as nans.
    required_headers = ['contributor', 'creator', 'date', 'description', 'identifier', 'language', 'publisher', 'relation', 'rights', 'subject', 'title', 'type']
    for column_name in required_headers:
        if column_name not in list(df.columns):
            df[column_name] = np.NaN

    # Crosswalk: Split contributor and creator columns into multiple (first, last at the pipes
    # TODO: For some reason it's splitting at every character, not at the pipes. Encoding issue?
    # PROBLEM! It's not all first/last data. What do you do with organizations?
    # Possibly use "where" to identify only rows which contain pipes?
    df['contributor'] = df['contributor'].astype('str')
    df['creator'] = df['creator'].astype('str')
    df['contributor'] = df.contributor.str.split("||")
    df['creator'] = df['creator'].str.split(pat="||", expand=False)

    # TODO: Split "description" into: Abstract||Provenance||Reason||Terms
    # PROBLEM! Not all fields have all data. How do you know which goes where?
    # TODO: Split the "date" field. May contain year, month, day. Fill blanks with NaNs.
    # TODO: Clean "identifier" so it only contains a URL. No other garbage nonsense.
    # TODO: Split "publisher"  City, ST: Publisher
    # TODO: Split "title" into title and subtitle at the colon :
    # TODO: Identify the relevant research type from "type" column
    # PROBLEM! Not all "type" data is useful! How do you identify the actual research type?
    return df


def reformat_author(authors: str) -> list:
    """
    Given a string with a variable length of author names, split into first/last fields.
    Handle name suffixes.
    TODO: Return an error with list of related IDs where organizations are listed instead of individuals.

    :param authors: A string containing 1+ author(s) separated by || double pipes
    :return: A list of tuples [('First', 'Last')]
    >>> reformat_author('Lindsey, Timothy C.||Ocker, Alisa G.||Miller, Gary D.||Miller, Michelle C., Jr.||')
    [('Timothy C.', 'Lindsey'), ('Alisa G.', 'Ocker'), ('Gary D.', 'Miller'), ('Michelle C.', 'Miller, Jr.')]
    >>> reformat_author('')
    ValueError: Author field appears to be blank.
    """
    reformatted_authors = []
    # if len(authors) < 1:
    #     # If the length of the full_author string is shorter than 1 character, skip. Prevent blank authors.
    #     raise ValueError("An author is missing. XML will not validate. Check your CSV file.")
    #else:
    authors_by_full_name = authors.split("||")
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
                print("NOTE: '{}' is not correctly formatted as 'Author Last Name, First Name'. XML will not validate. Check your CSV file.\n".format(split_author[0]))
            reformatted_authors.append((author_first, author_last))
    return reformatted_authors


def validate_internal_authors(author_list, netid_list) -> list:
    """
    TODO
    Need a way to give the person a unique ID - ideally NetID for internal persons. Right now using random ints.
    Read in a list of "First","Last","netID" from Pure
    Use fuzzy matching to compare with the names from IDEALS (author_list)
    Where a match is found, grab netID; else, generate random ID. Add each consecutively to unique_id list.

    :param author_list: A list of tuples with 1+ authors [('First','Last')]
    :param netid_list: List of first, last, netID
    :return: unique_id
    """
    pass


def write_author(author_list) -> str:
    """
    Given authors, insert into XML snippet, and return XML snippet.
    TODO: Add unique_id to function params, update random generator to insert values from unique_id list.

    :param author_list: A list of tuples with 1+ authors [('First','Last')]
    :return: XML snippet, containing first and last names of authors

    >>> write_author([('Timothy C.', 'Lindsey'), ('Alisa G.', 'Ocker'), ('Gary D.', 'Miller'), ('Michelle C.', 'Miller, Jr.')])
    <v1:author>
        <v1:role>author</v1:role>
        <v1:person id='person79358'>
            <v1:firstName>Timothy C.</v1:firstName>
            <v1:lastName>Lindsey</v1:lastName>
        </v1:person>
    </v1:author>
    <v1:author>
        <v1:role>author</v1:role>
        <v1:person id='person98417'>
            <v1:firstName>Alisa G.</v1:firstName>
            <v1:lastName>Ocker</v1:lastName>
        </v1:person>
    </v1:author>
    <v1:author>
        <v1:role>author</v1:role>
        <v1:person id='person37426'>
            <v1:firstName>Gary D.</v1:firstName>
            <v1:lastName>Miller</v1:lastName>
        </v1:person>
    </v1:author>
    <v1:author>
        <v1:role>author</v1:role>
        <v1:person id='person88344'>
             <v1:firstName>Michelle C.</v1:firstName>
             <v1:lastName>Miller, Jr.</v1:lastName>
        </v1:person>
    </v1:author>
    """
    authors_xml_snippet = ""
    # Add author to snippet
    for author in author_list:
        authors_xml_snippet += """
        <v1:author>
            <v1:role>author</v1:role>
            <v1:person id='person""" + str(random.randrange(0, 100000)) + """'>
                <v1:firstName>""" + author[0] + """</v1:firstName>
                <v1:lastName>""" + author[1] + """</v1:lastName>
            </v1:person>
        </v1:author>
        """
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


def write_series(all_series) -> str:
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


def write_xml(csv_data: list, managing_unit: str, organization_name: str, url_text: str, outfile_name: str):
    """
    Given csv data and the filename you want,
    Print data into an XML file, call helper functions depending on what columns are included in the data.

    :param csv_data: List of dictionaries. Each dict contains 1 research output.
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
        # Note here that "technical_report" type, peer review status, publication category, and publication status are hard coded.
        # Research Output ID
        print('<v1:book subType="technical_report" id="' + row['id'] + '">', file=outfile)
        print('<v1:peerReviewed>false</v1:peerReviewed>', file=outfile)
        print('<v1:publicationCategory>research</v1:publicationCategory>', file=outfile)
        print('<v1:publicationStatuses>', file=outfile)
        print('<v1:publicationStatus>', file=outfile)
        print('<v1:statusType>published</v1:statusType>', file=outfile)

        # Date
        print('<v1:date>', file=outfile)
        year = row['date'][:4]
        print('<v3:year>' + year + '</v3:year>', file=outfile)
        if len(row['date']) > 4:
            full_date = row['date'].split("-")
            month = full_date[1]
            print('<v3:month>' + month + '</v3:month>', file=outfile)
            if len(full_date) > 2:
                day = full_date[2]
                print('<v3:day>' + day + '</v3:day>', file=outfile)
        print('</v1:date>', file=outfile)
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
        print(write_author(authors), file=outfile)

        # Persons (group authors, organizational authors)
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
        print('<v1:owner id=",' + managing_unit + '"/>', file=outfile)

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
            if row['notes'] != "":
                print('''<v1:bibliographicalNotes>
                    <v1:bibliographicalNote>
                        <v3:text lang="en" country="US">''' + row['notes'] + '''</v3:text>
                    </v1:bibliographicalNote>
                </v1:bibliographicalNotes>''', file=outfile)

        # PAGINATION
        if 'pages' in csv_headers:
            if row['pages'] != "":
                print('<v1:numberOfPages>' + row['pages'] + '</v1:numberOfPages>', file=outfile)

        # Place of Publication
        if row['place of publication'] != "":
            print('''<v1:placeOfPublication>''' + row['place of publication'] + '''</v1:placeOfPublication>''', file=outfile)

        # SERIES
        if 'relation' in csv_headers:
            if row['relation'] != "":
                print('''<v1:series>''', file=outfile)
                print(write_series(row['relation']), file=outfile)
                print('''</v1:series>''', file=outfile)

        # PUBLISHER
        if row['publisher'] != "":
            print('''<v1:publisher>
              <v1:name>''' + row['publisher'] + '''</v1:name>
              </v1:publisher>''', file=outfile)

        # BOOK TYPE - Closing tag
        print('</v1:book>', file=outfile)

    # Print the document closing tag after completing the loop.
    print('</v1:publications>', file=outfile)
    outfile.close()

    # Print logic check to console.
    print("CSV contains {} research outputs.\n{} research outputs were saved to XML file.".format(total_research_outputs, counter))
    return outfile


if __name__ == '__main__':
    # Load the CSV file
    incoming_metadata = load_preformatted_csv("../ExpertsSCP/refactored_code/dummy_technical_report_data.csv")

    # Enter managing unit, organization name, and URL variables
    # TODO: Allow user to input the values for these variables
    mgr_unit = "123"
    org_name = "Illinois Sustainable Technology Center"
    url = "IDEALS repository link"

# Print the XML
    outgoing_xml = write_xml(incoming_metadata, mgr_unit, org_name, url, "test_outfile.xml")

# Create and inspect the dataframe returned
#     dc_metadata = load_dc_data("2142-812-dc.csv")
#     print(dc_metadata['creator'])
#     print(dc_metadata[['contributor','creator']][pd.isnull(dc_metadata['creator']) == False])
#     print(dc_metadata.dtypes)

# Search by ID (row index)
    # print(incoming_metadata[incoming_metadata.index == 46370])
