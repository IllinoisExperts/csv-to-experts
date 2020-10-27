# ideals-to-experts
IDEALS to Experts is a Python module that converts a CSV file of dc metadata records to valid XML for ingest by the Illinois Experts Research Information Management System.

### Roadmap
- Expand to include additional research output types (currently only supports technical reports).
- Allow user input for certain global fields.
- Add a way to insert NetID as personID.
- Possibly rework with pandas.

### Known issues
- "Contributor" field is currently ignored.
- Listing an organization as an author, instead of group author, will cause problems.
- Before running the script, encode or escape special characters in your CSV.  For example, insert encodings \&lt; for less than (<) and \&gt; for greater than (>).
This ensures they will not break the XML during validation.

### How to use
- Prepare a CSV file. See the template for required headers.  
- Afterwards, the XML outfile must be validated. 
- Then it is ready to be bulk uploaded in the Pure portal.

### Required fields
- All rows must have, at minimum, a year in the date field.
- All rows must have at least one author.

### For more information
For more information on preparing a data set for bulk uploading in Pure, see: https://experts.illinois.edu/admin/services/import/documentation.pdf 
