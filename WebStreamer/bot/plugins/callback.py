# ... top of file imports ...
import urllib.parse
# ... rest of imports ...

# inside gen_file_menu or callback where stream_link/page_link are built:
    page_link = f"{Var.URL}watch/{myfile_info['_id']}"
    safe_filename = urllib.parse.quote(myfile_info['file_name'])
    stream_link = f"{Var.URL}dl/{myfile_info['_id']}/{safe_filename}"

# use stream_link wherever download link was previously used
# ... rest of file unchanged ...