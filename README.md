# csv-to-experts
CSV to Experts is a Python module that converts a CSV file of either Zotero bibliographic metadata or dc metadata records to valid XML for ingest by the Illinois Experts Research Information Management System.

### Current Scope
Supported publication types:
- Technical Report
- Book
- Chapter in Book
- Journal Article
- Conference Proceeding

### Roadmap
- Allow user input for certain global fields.
- Fine tune the Internal Person matching. 
- Bulk import patents data; see patents branch. 

### Known issues
- "Contributor" field in dc metadata records is currently ignored.
- Before running the script, encode or escape special characters in your CSV.  For example, insert encodings \&lt; for less than (<) and \&gt; for greater than (>).
This ensures they will not break the XML during validation.

### How to use
- Export a CSV of citations from Zotero. Alternately, prepare a CSV file: See the template for required headers.  
- Follow the steps detailed in the package description to run the program. 
- Afterwards, the XML outfile must be validated. 
- Then it is ready to be bulk uploaded in the Pure portal.

### Required fields
- All rows must have, at minimum, a year in the date field.
- All rows must have at least one author.

### For more information
For more information on preparing a data set for bulk uploading in Pure, see: 
https://experts.illinois.edu/admin/services/import/documentation.pdf 
