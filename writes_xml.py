import xml.etree.ElementTree as et
import process_metadata as pm
from deduplicate_pubs import deduper
import os
# DEPENDENCIES:
# dependent external libraries: os, csv, json, requests, numpy, Leveshetin, pandas, ElementTree
# dependent internal libraries: deduplicate_pubs.py (uses resquests and json)
# process_metadata.py (uses csv, numpy, pandas, and Leveshetin), and api_keys.py (contains pure api keys)

# USAGE INSTRUCTIONS:
# INPUT: csv file with research output records, excel file of internal people downloaded from pure
# OUTPUT: an xml file for bulk import into Illinois Experts
# USE: automatically generate an xml file from a csv file for bulk uploading research output types
# chapter, conference paper, journal article, book, technical report, preprint, magazine article,
# and blog post into Experts


def main():
    print('Welcome to write_xml.py, a program ingests a csv file of research output records to be bulk uploaoded to Illinois Experts.')
    csv_file_name = input('Enter the complete path to the csv file you would like to process: ')
    while not os.path.isfile(csv_file_name) and csv_file_name != 'quit':
        csv_file_name = input('You did not enter a valid file path. Please enter the complete path to the csv file to continue, or enter \'quit\' to cancel the program: ')
    publications = pm.load_zotero_csv(csv_file_name)
    outfile_name = str(input('Enter the name for the xml file: ')) + '.xml'
    internal_persons = pm.access_internal_persons("/Users/elizabethschwartz/Documents/assistantships/scp/pri_import/pri_csv_to_xml_v1/data/Pure persons - 92322.xls")
    root = et.Element('publications')
    tree = et.ElementTree(root)
    root.set('xmlns', "v1.publication-import.base-uk.pure.atira.dk")
    root.set('xmlns:tns', "v3.commons.pure.atira.dk")
    outfile = open(outfile_name, 'wb')
    malformed_records = []
    duplicate_records = []
    for publication in publications:
        if deduper(publication):
            duplicate_records.append(publication)
        else:
            setting = pm.get_research_output_type(publication)
            if setting['subType'] == 'chapterInBook':
                record = write_chapterInBook_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'conference':
                record = write_conferencePaper_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'article':
                record = write_journal_article_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'technical_report':
                record = write_tech_report_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'preprint':
                record = write_preprint_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'book':
                record = write_book_xml(publication, root, setting, internal_persons)
                if record != None:
                    malformed_records.append(record['id'])
            elif setting['subType'] == 'magazine_newspaper_essay':
                record = write_magazine_article_xml(publication, root, setting, internal_persons)
                if record is not None:
                    malformed_records.append(record['id'])
            else:
                print(publication['type'])
                print(setting)
                print('Unsupported subtype.')
    tree.write(outfile)
    print('Attempted to write', len(publications), 'research outputs to xml.')
    print(str(len(malformed_records)) + '/' + str(len(publications)),'of these were not written to xml because they are missing required fields.')
    print(str(len(duplicate_records)) + '/' + str(len(publications)), 'of these were not written to xml because they are already in Experts.')
    print(len(publications) - len(malformed_records) - len(duplicate_records), 'total records were written to xml successfully.')
    if len(malformed_records) != 0:
        print('Correct the malformed records with the following ids, and rerun the program to include them in the xml file for bulk upload.')
        print(malformed_records)
    else:
        print('Proceed to Experts to bulk upload the file,', outfile_name)


def write_magazine_article_xml(publication, root, setting, internal_persons):
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str):
        mag_article = et.SubElement(root, 'other')
        mag_article.set('id', pm.get_id(publication))
        mag_article.set('subType', setting['subType'])
        peer_review = et.SubElement(mag_article, 'peerReviewed')
        peer_review.text = 'false'
        # publication status stuff!
        pub_statuses = et.SubElement(mag_article, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(mag_article, 'language')
        language.text = 'en_US'
        # title
        title = et.SubElement(mag_article, 'title')
        title_text = et.SubElement(title, 'tns:text')
        title_text.set('lang', 'en')
        title_text.set('country', 'US')
        title_text.text = pm.get_title(publication)
    #     abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(mag_article, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        # authors
        persons = et.SubElement(mag_article, 'persons')
        if type(pm.get_author_data(publication)) != float:
            the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
            for an_author in the_authors:
                this_author = et.SubElement(persons, 'author')
                role = et.SubElement(this_author, 'role')
                role.text = 'author'
                this_person = et.SubElement(this_author, 'person')
                this_person.set('id', str(an_author['author_id']))
                first_name = et.SubElement(this_person, 'firstName')
                first_name.text = an_author['author']['first_name']
                last_name = et.SubElement(this_person, 'lastName')
                last_name.text = an_author['author']['last_name']
                if type(an_author['unit_affiliation']) == str:
                    if 'imported' in str(an_author['author_id']):
                        pass
                    else:
                        organizations = et.SubElement(this_author, 'organisations')
                        organization = et.SubElement(organizations, 'organisation')
                        org_name = et.SubElement(organization, 'name')
                        org_name_text = et.SubElement(org_name, 'tns:text')
                        org_name_text.text = an_author['unit_affiliation']
                else:
                    pass
        else:
            pass
        the_organizations = et.SubElement(mag_article, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(mag_article, 'owner')
        owner.set('id', '3022427')

        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(mag_article, 'urls')
            # this has split the urls into letters :(
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            print(pm.get_url(publication))

        if type(pm.get_doi(publication)) == str:
            electronic_version_doi = et.SubElement(mag_article, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass

        # setting page ranges and number of pages
        if type(pm.get_pages_range(publication)) == str:
            the_pages = et.SubElement(mag_article, 'pages')
            the_pages.text = pm.get_pages_range(publication)
        else:
            pass
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(mag_article, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
            # setting host publisher
        if type(pm.get_journal(publication)) == str:
            publisher = et.SubElement(mag_article, 'publisher')
            publisher_name = et.SubElement(publisher, 'name')
            publisher_name.text = pm.get_journal(publication)
        else:
            pass
        if type(pm.get_volume(publication)) == str and type(pm.get_issn(publication)) == str:
             volume = et.SubElement(publisher, 'volume')
             volume.text = pm.get_volume(publication)
        else: pass
        if type(pm.get_issn(publication)) == str:
            issn = et.SubElement(publisher, 'printIssn')
            issn.text = pm.get_issn(publication)
    else:
        return publication


def write_book_xml(publication, root, setting, internal_persons):
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str):
        book = et.SubElement(root, "book")
        book.set('id', pm.get_id(publication))
        book.set('subType', setting['subType'])
        peer_review = et.SubElement(book, 'peerReviewed')
        peer_review.text = 'true'
        # pub status stuff
        pub_statuses = et.SubElement(book, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(book, 'language')
        language.text = 'en_US'
        # title
        title = et.SubElement(book, 'title')
        title_text = et.SubElement(title, 'tns:text')
        title_text.set('lang', 'en')
        title_text.set('country', 'US')
        title_text.text = pm.get_title(publication)
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(book, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        persons = et.SubElement(book, 'persons')
        if type(pm.get_author_data(publication)) != float:
            the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
            for an_author in the_authors:
                if type(an_author['author']['last_name']) != float:
                    this_author = et.SubElement(persons, 'author')
                    role = et.SubElement(this_author, 'role')
                    role.text = 'author'
                    this_person = et.SubElement(this_author, 'person')
                    this_person.set('id', str(an_author['author_id']))
                    first_name = et.SubElement(this_person, 'firstName')
                    first_name.text = an_author['author']['first_name']
                    last_name = et.SubElement(this_person, 'lastName')
                    last_name.text = an_author['author']['last_name']
                    if type(an_author['unit_affiliation']) == str:
                        if 'imported' in str(an_author['author_id']):
                            pass
                        else:
                            organizations = et.SubElement(this_author, 'organisations')
                            organization = et.SubElement(organizations, 'organisation')
                            org_name = et.SubElement(organization, 'name')
                            org_name_text = et.SubElement(org_name, 'tns:text')
                            org_name_text.text = an_author['unit_affiliation']
                    else: pass
                else: pass
        elif type(pm.get_editor_data(publication)) != float:
            the_editors = pm.get_internal_external_authors(pm.get_editor_data(publication), internal_persons, 79)
            for an_editor in the_editors:
                if type(an_editor['author']['last_name']) != float:
                    this_editor = et.SubElement(persons, 'author')
                    role = et.SubElement(this_editor, 'role')
                    role.text = 'editor'
                    this_person = et.SubElement(this_editor, 'person')
                    # this_person.set('id', str(an_editor['author_id']))
                    first_name = et.SubElement(this_person, 'firstName')
                    first_name.text = an_editor['author']['first_name']
                    last_name = et.SubElement(this_person, 'lastName')
                    last_name.text = an_editor['author']['last_name']
                    if type(an_editor['unit_affiliation']) == str and 'imported' in str(an_editor['author_id']):
                        organizations = et.SubElement(this_editor, 'organisations')
                        organization = et.SubElement(organizations, 'organisation')
                        org_name = et.SubElement(organization, 'name')
                        org_name_text = et.SubElement(org_name, 'tns:text')
                        org_name_text.text = an_editor['unit_affiliation']
                    else:
                        pass
                else: pass
        else:
            print('no author or editor. This will cause the upload to fail.')
            pass
        # setting organizational owner (pri)
        the_organizations = et.SubElement(book, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(book, 'owner')
        owner.set('id', '3022427')
        # if we get keywords, they should go here
        # keywords = et.SubElement(chapterInBook, 'keywords')
        # logicalGroup = et.SubElement(keywords, 'tns:logicalGroup')
        # structured_keywords = et.SubElement(logicalGroup, 'tns:structuredKeywords')
        # structured_keyword = et.SubElement(structured_keywords, 'tns:structuredKeyword')
        # free_keywords = et.SubElement(structured_keyword, 'tns:freeKeywords')
        # free_keyword = et.SubElement(free_keywords, 'tns:freeKeyword')
        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(book, 'urls')
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
           pass
        # setting doi
        if type(pm.get_doi(publication)) == str:
            electronic_version_doi = et.SubElement(book, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass
        # setting page ranges and number of pages
        if type(pm.get_pages_range(publication)) == str:
            the_pages = et.SubElement(book, 'pages')
            the_pages.text = pm.get_pages_range(publication)
        else:
            pass
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(book, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
        # setting print ISBNs- this will require manual data cleaning because
        # Susan's script has both print and electronic isbns in the same column
        if type(pm.get_isbn(publication)) == str:
            print_isbns = et.SubElement(book, 'printIsbns')
            isbn = et.SubElement(print_isbns, 'isbn')
            isbn.text = pm.get_isbn(publication)
        else:
            pass
        # setting publisher and series info if applicable
        if type(pm.get_volume(publication)) == str and type(pm.get_issn(publication)) == str and type(pm.get_publisher(publication)) == str:
            series = et.SubElement(book, 'series')
            this_series = et.SubElement(series, 'serie')
            publisher = et.SubElement(this_series, 'publisher')
            publisher_name = et.SubElement(publisher, 'publisherName')
            publisher_name.text = pm.get_publisher(publication)
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        elif type(pm.get_publisher(publication)) == str:
            publisher = et.SubElement(book, 'publisher')
            publisher_name = et.SubElement(publisher, 'name')
            publisher_name.text = pm.get_publisher(publication)
        else: pass
    else:
        return publication


def write_preprint_xml(publication, root, setting, internal_persons):
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str):
        preprint = et.SubElement(root, 'workingPaper')
        preprint.set('id', pm.get_id(publication))
        preprint.set('subType', 'preprint')
        peer_review = et.SubElement(preprint, 'peerReviewed')
        peer_review.text = 'false'
        # pub status
        pub_statuses = et.SubElement(preprint, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'inprep'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(preprint, 'language')
        language.text = 'en_US'
        # title
        if type(pm.get_title(publication)) == str:
            title = et.SubElement(preprint, 'title')
            title_text = et.SubElement(title, 'tns:text')
            title_text.set('lang', 'en')
            title_text.set('country', 'US')
            title_text.text = pm.get_title(publication)
        else:
            print('research output', pm.get_id(publication), 'is missing required title field. upload will fail.')
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(preprint, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        # authors
        persons = et.SubElement(preprint, 'persons')
        the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
        for an_author in the_authors:
            this_author = et.SubElement(persons, 'author')
            role = et.SubElement(this_author, 'role')
            role.text = 'author'
            this_person = et.SubElement(this_author, 'person')
            this_person.set('id', str(an_author['author_id']))
            if type(an_author['author']['first_name']) == str:
                first_name = et.SubElement(this_person, 'firstName')
                first_name.text = an_author['author']['first_name']
            else:
                pass
            last_name = et.SubElement(this_person, 'lastName')
            last_name.text = an_author['author']['last_name']
            if type(an_author['unit_affiliation']) == str:
                if 'imported' in str(an_author['author_id']):
                    pass
                else:
                    organizations = et.SubElement(this_author, 'organisations')
                    organization = et.SubElement(organizations, 'organisation')
                    org_name = et.SubElement(organization, 'name')
                    org_name_text = et.SubElement(org_name, 'tns:text')
                    org_name_text.text = an_author['unit_affiliation']
            else:
                pass
        # setting organizational owner (pri)
        the_organizations = et.SubElement(preprint, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(preprint, 'owner')
        owner.set('id', '3022427')
        # urls
        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(preprint, 'urls')
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            pass
            # doi
        if type(pm.get_doi(publication)) == str:
            electronic_versions = et.SubElement(preprint, 'electronicVersions')
            electronic_version_doi = et.SubElement(electronic_versions, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass
            # print(pm.get_doi(publication))
            # setting page ranges and number of pages
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(preprint, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
    else:
        return publication


def write_tech_report_xml(publication, root, setting, internal_persons):
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str):
        tech_report = et.SubElement(root, 'book')
        tech_report.set('id', pm.get_id(publication))
        tech_report.set('subType', 'technical_report')
        peer_review = et.SubElement(tech_report, 'peerReviewed')
        peer_review.text = 'false'
        # pub status
        pub_statuses = et.SubElement(tech_report, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(tech_report, 'language')
        language.text = 'en_US'
        # title
        if type(pm.get_title(publication)) == str:
            title = et.SubElement(tech_report, 'title')
            title_text = et.SubElement(title, 'tns:text')
            title_text.set('lang', 'en')
            title_text.set('country', 'US')
            title_text.text = pm.get_title(publication)
        else:
            print('research output', pm.get_id(publication), 'is missing required title field. upload will fail.')
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(tech_report, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        # authors
        persons = et.SubElement(tech_report, 'persons')
        if type(pm.get_author_data(publication)) == float:
            an_author = et.SubElement(persons, 'author')
            role = et.SubElement(an_author, 'role')
            role.text = 'author'
            organizations = et.SubElement(an_author, 'organisations')
            organization = et.SubElement(organizations, 'organisation')
            organization.set('id', '3022427')
            org_name = et.SubElement(organization, 'name')
            org_name_text = et.SubElement(org_name, 'tns:text')
            org_name_text.text = 'Prairie Research Institute'

        else:
            # persons = et.SubElement(tech_report, 'persons')
            the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
            for an_author in the_authors:
                this_author = et.SubElement(persons, 'author')
                role = et.SubElement(this_author, 'role')
                role.text = 'author'
                this_person = et.SubElement(this_author, 'person')
                this_person.set('id', str(an_author['author_id']))
                if type(an_author['author']['first_name']) == str:
                    first_name = et.SubElement(this_person, 'firstName')
                    first_name.text = an_author['author']['first_name']
                else:
                    pass
                last_name = et.SubElement(this_person, 'lastName')
                last_name.text = an_author['author']['last_name']
                if type(an_author['unit_affiliation']) == str:
                    if 'imported' in str(an_author['author_id']):
                        pass
                    else:
                        organizations = et.SubElement(this_author, 'organisations')
                        organization = et.SubElement(organizations, 'organisation')
                        org_name = et.SubElement(organization, 'name')
                        org_name_text = et.SubElement(org_name, 'tns:text')
                        org_name_text.text = an_author['unit_affiliation']
                else:
                    pass
        # setting organizational owner (pri)
        the_organizations = et.SubElement(tech_report, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(tech_report, 'owner')
        owner.set('id', '3022427')
        # urls
        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(tech_report, 'urls')
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            pass
            # print(pm.get_url(publication))
        # doi
        if type(pm.get_doi(publication)) == str:
            electronic_versions = et.SubElement(tech_report, 'electronicVersions')
            electronic_version_doi = et.SubElement(electronic_versions, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass
            # print(pm.get_doi(publication))
        # setting page ranges and number of pages
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(tech_report, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
        if type(pm.get_isbn(publication)) == str:
            print_isbns = et.SubElement(tech_report, 'printIsbns')
            isbn = et.SubElement(print_isbns, 'isbn')
            isbn.text = pm.get_isbn(publication)
            print(pm.get_isbn(publication))
        else:
            pass
        if type(pm.get_publisher(publication)) == str:
            publisher = et.SubElement(tech_report, 'publisher')
            publisher_name = et.SubElement(publisher, 'name')
            publisher_name.text = pm.get_publisher(publication)
        else:
            pass
        if type(pm.get_volume(publication)) == str and type(pm.get_issn(publication)) == str:
            series = et.SubElement(tech_report, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        elif type(pm.get_volume(publication)) == str:
            series = et.SubElement(tech_report, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
        elif type(pm.get_issn(publication)) == str:
            series = et.SubElement(tech_report, 'series')
            this_series = et.SubElement(series, 'serie')
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        else:
            pass
    else:
        return publication


def write_journal_article_xml(publication, root, setting, internal_persons):
    # journal article type requires fields: pub year, article title, authors, language, and journal title
    # this script will remove any pubs not fitting these criteria
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str) and (type(pm.get_journal(publication))== str):
        journal_contribution = et.SubElement(root, 'contributionToJournal')
        journal_contribution.set('id', pm.get_id(publication))
        journal_contribution.set('subType', 'article')
        peer_review = et.SubElement(journal_contribution, 'peerReviewed')
        peer_review.text = 'true'
        # pub status
        pub_statuses = et.SubElement(journal_contribution, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(journal_contribution, 'language')
        language.text = 'en_US'
        # title
        if type(pm.get_title(publication)) == str:
            title = et.SubElement(journal_contribution, 'title')
            title_text = et.SubElement(title, 'tns:text')
            title_text.set('lang', 'en')
            title_text.set('country', 'US')
            title_text.text = pm.get_title(publication)
        else:
            print('research output', pm.get_id(publication), 'is missing required title field. upload will fail.')
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(journal_contribution, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        # authors
        persons = et.SubElement(journal_contribution, 'persons')
        the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
        for an_author in the_authors:
            this_author = et.SubElement(persons, 'author')
            role = et.SubElement(this_author, 'role')
            role.text = 'author'
            this_person = et.SubElement(this_author, 'person')
            this_person.set('id', str(an_author['author_id']))
            if type(an_author['author']['first_name']) == str:
                first_name = et.SubElement(this_person, 'firstName')
                first_name.text = an_author['author']['first_name']
            else:
                pass
            last_name = et.SubElement(this_person, 'lastName')
            last_name.text = an_author['author']['last_name']
            if type(an_author['unit_affiliation']) == str:
                if 'imported' in str(an_author['author_id']):
                    pass
                else:
                    organizations = et.SubElement(this_author, 'organisations')
                    organization = et.SubElement(organizations, 'organisation')
                    org_name = et.SubElement(organization, 'name')
                    org_name_text = et.SubElement(org_name, 'tns:text')
                    org_name_text.text = an_author['unit_affiliation']
            else:
                pass
        # setting organizational owner (pri)
        the_organizations = et.SubElement(journal_contribution, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(journal_contribution, 'owner')
        owner.set('id', '3022427')
        # urls
        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(journal_contribution, 'urls')
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            pass
            # print(pm.get_url(publication))
        # doi
        if type(pm.get_doi(publication)) == str:
            electronic_versions = et.SubElement(journal_contribution, 'electronicVersions')
            electronic_version_doi = et.SubElement(electronic_versions, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass
            # print(pm.get_doi(publication))
        # setting page ranges and number of pages
        if type(pm.get_pages_range(publication)) == str:
            the_pages = et.SubElement(journal_contribution, 'pages')
            the_pages.text = pm.get_pages_range(publication)
        else:
            pass
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(journal_contribution, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass

        if type(pm.get_issue(publication)) == str:
            issue_number = et.SubElement(journal_contribution, 'journalNumber')
            issue_number.text = pm.get_issue(publication)
        else:
            pass
        if type(pm.get_volume(publication)) == str:
            volume_number = et.SubElement(journal_contribution, 'journalVolume')
            volume_number.text = pm.get_volume(publication)
        else:
            pass
        # journal metadata (title, issn)

        if type(pm.get_journal(publication)) == str:
            journal = et.SubElement(journal_contribution, 'journal')
            journal_title = et.SubElement(journal, 'title')
            journal_title.text = pm.get_journal(publication)
        else:
            print('research output', pm.get_id(publication), 'is missing required journal field. upload will fail.')
        these_issns = pm.get_issn(publication)
        if type(these_issns) == list:
            issns = et.SubElement(journal, 'printIssns')
            for this_issn in these_issns:
                issn = et.SubElement(issns, 'issn')
                issn.text = this_issn
        else:
            pass
    else:
        return publication


def write_conferencePaper_xml(publication, root, setting, internal_persons):
    # conference paper has required types pub year, language, title, author, managing unit, and host pub title
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str) and (
            type(pm.get_journal(publication)) == str):
        conferenceContribution = et.SubElement(root, "chapterInBook")
        conferenceContribution.set('id', pm.get_id(publication))
        conferenceContribution.set('subType', 'conference')
        peer_review = et.SubElement(conferenceContribution, 'peerReviewed')
        peer_review.text = 'false'
        # pub status stuff
        pub_statuses = et.SubElement(conferenceContribution, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(conferenceContribution, 'language')
        language.text = 'en_US'
        # title
        if type(pm.get_title(publication)) == str:
            title = et.SubElement(conferenceContribution, 'title')
            title_text = et.SubElement(title, 'tns:text')
            title_text.set('lang', 'en')
            title_text.set('country', 'US')
            title_text.text = pm.get_title(publication)
        else:
            print('research output', pm.get_id(publication), 'is missing required title field. upload will fail.')
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(conferenceContribution, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        persons = et.SubElement(conferenceContribution, 'persons')
        the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
        for an_author in the_authors:
            this_author = et.SubElement(persons, 'author')
            role = et.SubElement(this_author, 'role')
            role.text = 'author'
            this_person = et.SubElement(this_author, 'person')
            this_person.set('id', str(an_author['author_id']))
            if type(an_author['author']['first_name']) == str:
                first_name = et.SubElement(this_person, 'firstName')
                first_name.text = an_author['author']['first_name']
            else:
                pass
            last_name = et.SubElement(this_person, 'lastName')
            last_name.text = an_author['author']['last_name']
            if type(an_author['unit_affiliation']) == str:
                if 'imported' in str(an_author['author_id']):
                    pass
                else:
                    organizations = et.SubElement(this_author, 'organisations')
                    organization = et.SubElement(organizations, 'organisation')
                    org_name = et.SubElement(organization, 'name')
                    org_name_text = et.SubElement(org_name, 'tns:text')
                    org_name_text.text = an_author['unit_affiliation']
            else:
                pass

        # setting organizational owner (pri)
        the_organizations = et.SubElement(conferenceContribution, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(conferenceContribution, 'owner')
        owner.set('id', '3022427')

        # if we get keywords, they should go here
        # keywords = et.SubElement(conferenceContribution, 'keywords')
        # logicalGroup = et.SubElement(keywords, 'tns:logicalGroup')
        # structured_keywords = et.SubElement(logicalGroup, 'tns:structuredKeywords')
        # structured_keyword = et.SubElement(structured_keywords, 'tns:structuredKeyword')
        # free_keywords = et.SubElement(structured_keyword, 'tns:freeKeywords')
        # free_keyword = et.SubElement(free_keywords, 'tns:freeKeyword')

        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(conferenceContribution, 'urls')
            # this has split the urls into letters :(
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            pass
            # print(pm.get_url(publication))

        if type(pm.get_doi(publication)) == str:
            electronic_versions = et.SubElement(conferenceContribution, 'electronicVersions')
            electronic_version_doi = et.SubElement(electronic_versions, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'closed'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass
            # print(pm.get_doi(publication))

        # setting page ranges and number of pages
        if type(pm.get_pages_range(publication)) == str:
            the_pages = et.SubElement(conferenceContribution, 'pages')
            the_pages.text = pm.get_pages_range(publication)
        else:
            pass
            # print(pm.get_pages_range(publication))
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(conferenceContribution, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
            # print(pm.get_number_pages(publication))
        # setting print ISBNs- this will require manual data cleaning because
        # Susan's script has both print and electronic isbns in the same column
        # right now
        if type(pm.get_isbn(publication)) == str:
            print_isbns = et.SubElement(conferenceContribution, 'printIsbns')
            isbn = et.SubElement(print_isbns, 'isbn')
            isbn.text = pm.get_isbn(publication)
            # print(pm.get_isbn(publication))
        else:
            pass
        # setting host publication (book/anthology title)
        host_pub = et.SubElement(conferenceContribution, 'hostPublicationTitle')
        try:
            host_pub.text = str(pm.get_journal(publication))
        except TypeError:
            print('there is no host publication title. this is a required field. upload will fail.')
        if type(pm.get_publisher(publication)) == str:
            publisher = et.SubElement(conferenceContribution, 'publisher')
            publisher_name = et.SubElement(publisher, 'name')
            publisher_name.text = pm.get_publisher(publication)
        else:
            pass
            # print(pm.get_publisher(publication))
        if type(pm.get_volume(publication)) == str and type(pm.get_issn(publication)) == str:
            series = et.SubElement(conferenceContribution, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        elif type(pm.get_volume(publication)) == str:
            series = et.SubElement(conferenceContribution, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
        elif type(pm.get_issn(publication)) == str:
            series = et.SubElement(conferenceContribution, 'series')
            this_series = et.SubElement(series, 'serie')
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        else:
            pass
    else:
        return publication


def write_chapterInBook_xml(publication, root, setting, internal_persons):
    if (type(pm.get_publication_year(publication)) == int) and (type(pm.get_title(publication)) == str) and (
            type(pm.get_journal(publication)) == str):
        chapterInBook = et.SubElement(root, "chapterInBook")
        chapterInBook.set('id', pm.get_id(publication))
        chapterInBook.set('subType', setting['subType'])
        peer_review = et.SubElement(chapterInBook, 'peerReviewed')
        peer_review.text = 'true'
        # pub status stuff
        pub_statuses = et.SubElement(chapterInBook, 'publicationStatuses')
        pub_status = et.SubElement(pub_statuses, 'publicationStatus')
        status_type = et.SubElement(pub_status, 'statusType')
        status_type.text = 'published'
        date = et.SubElement(pub_status, 'date')
        the_year = et.SubElement(date, 'tns:year')
        if type(pm.get_publication_year(publication)) != float:
            the_year.text = str(pm.get_publication_year(publication))
        else:
            print('research output', pm.get_id(publication), 'is missing required year field. upload will fail.')
        # language
        language = et.SubElement(chapterInBook, 'language')
        language.text = 'en_US'
        # title
        title = et.SubElement(chapterInBook, 'title')
        title_text = et.SubElement(title, 'tns:text')
        title_text.set('lang', 'en')
        title_text.set('country', 'US')
        title_text.text = pm.get_title(publication)
        # abstract
        if type(pm.get_abstract(publication)) == str:
            abstract = et.SubElement(chapterInBook, 'abstract')
            abstract_text = et.SubElement(abstract, 'tns:text')
            abstract_text.set('lang', 'en')
            abstract_text.set('country', 'US')
            abstract_text.text = pm.get_abstract(publication)
        else:
            pass
        persons = et.SubElement(chapterInBook, 'persons')
        the_authors = pm.get_internal_external_authors(pm.get_author_data(publication), internal_persons, 79)
        for an_author in the_authors:
            this_author = et.SubElement(persons, 'author')
            role = et.SubElement(this_author, 'role')
            role.text = 'author'
            this_person = et.SubElement(this_author, 'person')
            this_person.set('id', str(an_author['author_id']))
            first_name = et.SubElement(this_person, 'firstName')
            first_name.text = an_author['author']['first_name']
            last_name = et.SubElement(this_person, 'lastName')
            last_name.text = an_author['author']['last_name']
            if type(an_author['unit_affiliation']) == str:
                if 'imported' in str(an_author['author_id']):
                    pass
                else:
                    organizations = et.SubElement(this_author, 'organisations')
                    organization = et.SubElement(organizations, 'organisation')
                    org_name = et.SubElement(organization, 'name')
                    org_name_text = et.SubElement(org_name, 'tns:text')
                    org_name_text.text = an_author['unit_affiliation']
            else:
                pass

        # setting organizational owner (pri)
        the_organizations = et.SubElement(chapterInBook, 'organisations')
        the_organization = et.SubElement(the_organizations, 'organisation')
        the_organization.set('id', '3022427')
        owner = et.SubElement(chapterInBook, 'owner')
        owner.set('id', '3022427')

        # if we get keywords, they should go here
        # keywords = et.SubElement(chapterInBook, 'keywords')
        # logicalGroup = et.SubElement(keywords, 'tns:logicalGroup')
        # structured_keywords = et.SubElement(logicalGroup, 'tns:structuredKeywords')
        # structured_keyword = et.SubElement(structured_keywords, 'tns:structuredKeyword')
        # free_keywords = et.SubElement(structured_keyword, 'tns:freeKeywords')
        # free_keyword = et.SubElement(free_keywords, 'tns:freeKeyword')

        if type(pm.get_url(publication)) == str:
            these_urls = pm.get_url(publication).split(';')
            urls = et.SubElement(chapterInBook, 'urls')
            # this has split the urls into letters :(
            for this_url in these_urls:
                url = et.SubElement(urls, 'url')
                a_url = et.SubElement(url, 'url')
                a_url.text = this_url
                description = et.SubElement(url, 'description')
                description_text = et.SubElement(description, 'tns:text')
                description_text.text = 'Other Link'
                url_type = et.SubElement(url, 'type')
                url_type.text = 'unspecified'
        else:
            print(pm.get_url(publication))

        if type(pm.get_doi(publication)) == str:
            electronic_version_doi = et.SubElement(chapterInBook, 'electronicVersionDOI')
            doi_version = et.SubElement(electronic_version_doi, 'version')
            doi_version.text = "publishersversion"
            # licence = et.SubElement(electronic_version_doi, 'licence')
            public_access = et.SubElement(electronic_version_doi, 'publicAccess')
            public_access.text = 'unknown'
            the_doi = et.SubElement(electronic_version_doi, 'doi')
            the_doi.text = str(pm.get_doi(publication))
        else:
            pass

        # setting page ranges and number of pages
        if type(pm.get_pages_range(publication)) == str:
            the_pages = et.SubElement(chapterInBook, 'pages')
            the_pages.text = pm.get_pages_range(publication)
        else:
            pass
        if type(pm.get_number_pages(publication)) == str:
            number_pages = et.SubElement(chapterInBook, 'numberOfPages')
            number_pages.text = pm.get_number_pages(publication)
        else:
            pass
        # setting print ISBNs- this will require manual data cleaning because
        # Susan's script has both print and electronic isbns in the same column
        # right now
        if type(pm.get_isbn(publication)) == str:
            print_isbns = et.SubElement(chapterInBook, 'printIsbns')
            isbn = et.SubElement(print_isbns, 'isbn')
            isbn.text = pm.get_isbn(publication)
            print(pm.get_isbn(publication))
        else:
            pass
        # setting host publication (book/anthology title)
        host_pub = et.SubElement(chapterInBook, 'hostPublicationTitle')
        try:
            host_pub.text = str(pm.get_journal(publication))
        except TypeError:
            print('there is no host publication title. this is a required field. upload will fail.')
        if type(pm.get_publisher(publication)) == str:
            publisher = et.SubElement(chapterInBook, 'publisher')
            publisher_name = et.SubElement(publisher, 'name')
            publisher_name.text = pm.get_publisher(publication)
        else:
            pass
        if type(pm.get_volume(publication)) == str and type(pm.get_issn(publication)) == str:
            series = et.SubElement(chapterInBook, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        elif type(pm.get_volume(publication)) == str:
            series = et.SubElement(chapterInBook, 'series')
            this_series = et.SubElement(series, 'serie')
            volume = et.SubElement(this_series, 'volume')
            volume.text = pm.get_volume(publication)
            if type(pm.get_issue(publication)) == str:
                issue = et.SubElement(this_series, 'number')
                issue.text = pm.get_issue(publication)
            else:
                pass
        elif type(pm.get_issn(publication)) == str:
            series = et.SubElement(chapterInBook, 'series')
            this_series = et.SubElement(series, 'serie')
            issn = et.SubElement(this_series, 'printIssn')
            issn.text = pm.get_issn(publication)
        else:
            pass
    else:
        return publication
main()

