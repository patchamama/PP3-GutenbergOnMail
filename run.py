import gspread
from google.oauth2.service_account import Credentials
import os
import urllib.request
import re
from datetime import date
from copy import deepcopy

MENU_OPTIONS_TEMPLATE = """
|--------------------------------------------------------
| {search_conditions}
| Books: {books_found}
| {unique_book_val}
|----- One condition (+ Conditions reset) ---------------
|      1. Search in any field (author or title)
|      2. Search a book for ID-Number
|----- Multiple conditions (<AND> operator) -------------
|      3. Add a author condition
|      4. Add a title condition
|      5. Add a language condition
|--------------------------------------------------------
|      6. Reset conditions
|      7. Show results
|--------------------------------------------------------
|      8. Send an ebook (epub) to email
|      9. See Statistics of requests
|--------------------------------------------------------"""

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

CREDS = Credentials.from_service_account_file("creds.json")
SCOPED_CREDS = CREDS.with_scopes(SCOPE)
GSPREAD_CLIENT = gspread.authorize(SCOPED_CREDS)
SHEET = GSPREAD_CLIENT.open("GutenbergOnMail")
print("Opening catalog data...")
catalog = SHEET.worksheet("pg_catalog")
catalog_data = []  # All data to work (of the sheet)
filtered_data = []  # Result of data after filter ON
cond_total = []  # All the conditions defined (filter)


def get_filter_data(data, filter=[], and_cond=True):
    """
    Filter all data based on the condition of the
    specified fields passed in the <filter> parameter.
    """
    all_data = []
    if len(filter) > 0:
        for record in data:
            passConds = and_cond  # If True: <cond> and <cond>, if False: or
            for cond in filter:
                if "OPERATOR" in cond:
                    and_cond = cond["OPERATOR"] == "and"
                for fieldcond, valcond in cond.items():
                    if fieldcond != "OPERATOR":
                        try:
                            if isinstance(valcond, int):
                                if and_cond:
                                    passConds = (
                                        record[fieldcond] == valcond
                                    ) and (passConds)
                                else:  # or
                                    passConds = (
                                        record[fieldcond] == valcond
                                    ) or (passConds)
                            else:  # is string
                                if and_cond:
                                    passConds = (
                                        valcond.lower()
                                        in record[fieldcond].lower()
                                    ) and (passConds)
                                else:  # or
                                    passConds = (
                                        valcond.lower()
                                        in record[fieldcond].lower()
                                    ) or (passConds)
                        except AttributeError:
                            if and_cond:
                                passConds = (
                                    record[fieldcond] == valcond
                                ) and (passConds)
                            else:  # or
                                passConds = (
                                    record[fieldcond] == valcond
                                ) or (passConds)
            if passConds:
                all_data.append(record)
    else:
        all_data = data
    return all_data


def print_data(data):
    """
    Print the fields Id, Authors, Title, Language with
    table format to see the result tabulated in the terminal
    """
    data_lang_stat = {}

    print(
        "\n{:5s} | {:30s} | {:30s} | {:4s}".format(
            "Id", "Author", "Title", "Lang"
        )
    )
    print("".ljust(80, "-"))

    for record in data:
        vlang = record["Language"]
        data_lang_stat[vlang] = (
            (data_lang_stat[vlang] + 1)
            if (vlang in data_lang_stat)
            else 1
        )
        record["Title"] = str(record["Title"]).replace(
            "\n", ""
        )  # Some record['Title'] are int
        tit = record["Title"]
        aut = record['Authors']
        id = record['Text#']
        lang = record['Language']
        print(
            f"{id:5d} | {aut[:30]:30s} | {tit[:30]:30s} | {lang:4s}"
        )
    if len(data_lang_stat) > 0:
        print("Languages found:", end=" ")
        for vlang, num in data_lang_stat.items():
            print(f"{vlang} ({num})", end=" ")
        print()


def download_ebook(id, with_images=False, format="epub"):
    """
    Download a epub file from the Gutenberg website with
    one number (id) = Text#
    """
    # Examples:
    # https://www.gutenberg.org/ebooks/62187.epub.images
    # https://www.gutenberg.org/ebooks/62187.epub3.images
    # https://www.gutenberg.org/ebooks/62187.epub.noimages
    urlimage = "images" if (with_images) else "noimages"
    url_ebook = f"https://www.gutenberg.org/ebooks/{id}.{format}.{urlimage}"
    print(url_ebook)
    try:
        web_file = urllib.request.urlopen(url_ebook).read()
        file_name = f"{id}.epub"
        epub_local = open(file_name, "wb")
        epub_local.write(web_file)
        epub_local.close()
        return file_name
    except HTTPError:
        pause("Error downloading the file")
        return None


def get_all_records(catalog):
    """
    Return all the data of the Catalog/sheet
    """
    print("Pre-loading all books...")
    data = catalog.get_all_records()
    return data


def pause(msg=""):
    """
    Show message while wait in the terminal
    """
    if len(msg) > 0:
        print(msg)
    input("\nPress enter to continue...\n")


def clear_terminal():
    """
    Clear the terminal (reset)
    """
    os.system("cls" if os.name == "nt" else "clear")


def valid_email(email_address):
    """
    Validate if the email address is valid
    """
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return re.fullmatch(regex, email_address)


def update_request_ebook_fname(worksheet_name, ebook_id, type_request):
    """
    Update request worksheet with the ebook_id request,
    type_request: [terminal/mail] and date
    """
    data_to_save = []
    data_to_save.append(ebook_id)
    data_to_save.append(type_request)
    data_to_save.append(str(date.today()))
    print(f"Updating {worksheet_name} in worksheet...\n")
    worksheet_to_work = SHEET.worksheet(worksheet_name)
    worksheet_to_work.append_row(data_to_save)
    print(f"{worksheet_name} worksheet updated successfully\n")


def get_info_from_data(book_id):
    """
    Return the data from a book_id in the catalog data
    """
    global catalog_data
    for record in catalog_data:
        if book_id == int(record["Text#"]):
            return record["Authors"], record["Title"], record["Language"]
    return "-", "-", "-"


def show_request_statistics():
    """
    Check and show statistics of request (send per email)
    """
    global catalog_data
    count_author_books = {}
    count_author_requests = {}
    cant_books_req = {}

    requests_worksheet = SHEET.worksheet("requests")
    requests_vals = requests_worksheet.get_all_records()

    for request_data in requests_vals:
        vid = int(request_data["Text#"])
        cant_books_req[vid] = (
            (cant_books_req[vid] + 1) if vid in cant_books_req else 1
        )

    cant_books_req = sorted(
        cant_books_req.items(), key=lambda x: x[1], reverse=True
    )
    print("\nNumber of requests per book")
    print("".ljust(74, "-"))
    print(
        "{:5s} | {:5s} | {:20s} | {:29s} | {:4s}".format(
            "Id", "Count", "Author", "Title", "Lang"
        )
    )
    print("".ljust(74, "-"))
    for val_books in cant_books_req:
        no_book = val_books[0]
        count_books = val_books[1]
        vaut, vtit, vlang = get_info_from_data(no_book)
        print(
            f"{no_book:5d} | {count_books:5d} | {vaut[:20]:20s}" +
            f" | {vtit[:29]:29s} | {vlang:4s}"
        )
        count_author_requests[vaut] = (
            (count_author_requests[vaut] + count_books)
            if vaut in count_author_requests
            else count_books
        )
        count_author_books[vaut] = (
            (count_author_books[vaut] + 1)
            if vaut in count_author_books
            else 1
        )

    print("\nNumber of requests per author")
    print("".ljust(74, "-"))
    print("{:50s} | {:5s}".format("Author", "Requests"))
    print("".ljust(74, "-"))
    count_author_requests = sorted(
        count_author_requests.items(), key=lambda x: x[1], reverse=True
    )
    for val_books in count_author_requests:
        author_name = val_books[0]
        count_books = val_books[1]
        print(f"{author_name[:50]:50s} | {count_books:5d}")

    print("\nNumber of books per author")
    print("".ljust(74, "-"))
    print("{:50s} | {:5s}".format("Author", "Books"))
    print("".ljust(74, "-"))
    count_author_books = sorted(
        count_author_books.items(), key=lambda x: x[1], reverse=True
    )
    for val_books in count_author_books:
        author_name = val_books[0]
        count_books = val_books[1]
        print(f"{author_name[:50]:50s} | {count_books:5d}")
    pause()


def send_ebook_mailto(email_address, ebook_id):
    """
    Send the ebook to the email address specified
    """
    # ebook_fname = download_ebook(ebook_id)
    # os.remove(ebook_fname)
    update_request_ebook_fname("requests", ebook_id, "terminal")
    # TODO: send to actual email later...


def clean_search(search_string):
    """
    Remove characters/symbols for better search: ()"'#-_[]...
    """
    for a in "()\"'#-_[]$!¿?=/&+%.,;":
        search_string = search_string.replace(a, " ")
    while "  " in search_string:
        search_string = search_string.replace("  ", " ")
    return search_string.lower().strip()


def get_conditions_pretty(conditions):
    """
    Returns the conditions in a more readable format
    """
    # print(conditions)
    str_conditions = ""
    cant_items = 0
    if len(conditions) == 0:
        return "No defined condition"
    for (
        items
    ) in (
        conditions
    ):  # List of items with conditions [({'Authors': 'shakes'},...
        cant_items += 1
        cant_cond = 0
        srt_operator = "or"
        if cant_items > 1:
            str_conditions += (
                " and "  # by default the relation between conds add are "and"
            )
        str_conditions += "("
        for (
            cond
        ) in (
            items
        ):  # Every item with one cond: ({'Authors': 'shakes'},...
            if "OPERATOR" in cond:
                srt_operator = ("and") if cond["OPERATOR"] == "and" else "or"
            for fname, fval in cond.items():
                if fname != "OPERATOR":
                    cant_cond += 1
                    if cant_cond > 1:
                        str_conditions += " " + srt_operator + " "
                    str_conditions += f'{fname}="{fval}"'
        str_conditions += ")"
    return str_conditions


def wrap_string_atpos(st, initstring, atpos):
    """
    Wrap a string to show well formated
    """
    endstring = ""
    if len(st) <= atpos:
        return st
    while len(st) > atpos:
        right = " "
        for a in range(atpos, 0, -1):
            if a == 1:
                endstring += st if len(endstring) == 0 else "\n" + st
                return endstring
            if right == " ":
                if st[a] == " ":
                    left, right = st[:a], st[a:]
                    endstring += left if len(endstring) == 0 else "\n" + left
                    st = initstring + right
    endstring += st if len(endstring) == 0 else "\n" + st
    return endstring


def query_field(prompt, conditions, reset_filter=False, input_as_string=True):
    """
    Input the value of the field and predefine the value of the conditions
    fields and execute the filter
    """
    global catalog_data
    global cond_total
    global filtered_data

    search_cond = input(prompt)
    if input_as_string:
        search_cond = clean_search(search_cond)
    else:
        try:
            test = int(search_cond)
        except ValueError:
            pause(
                "Error: the value is not a number integer..."
            )
            return

    if len(search_cond) > 0:
        if reset_filter:
            filtered_data = catalog_data  # Reset all the conditions
            cond_total.clear()
        list_words_search = search_cond.split()
        for word in list_words_search:
            partial_cond = deepcopy(conditions)
            for cond_val in partial_cond:
                for vcond, vval in cond_val.items():
                    if cond_val != "OPERATOR":
                        if input_as_string:
                            cond_val[vcond] = word
                        else:
                            cond_val[vcond] = int(word)
            cond_total.append(partial_cond)
            filtered_data = get_filter_data(filtered_data, list(partial_cond))
        if len(filtered_data) == 0:
            pause(f"No data found with the conditions: {search_cond}")
        else:
            print_data(filtered_data)
            pause()


def show_menu():
    """
    Show Main Menu
    """
    global catalog_data
    global cond_total
    global filtered_data

    catalog_data = get_all_records(catalog)
    filtered_data = catalog_data
    NO_ACTION = "Not applicable. It is not possible to filter further books"

    while True:
        clear_terminal()
        vtemp = ""
        if len(filtered_data) == 1:
            id = filtered_data[0]['Text#']
            aut = filtered_data[0]['Authors']
            tit = filtered_data[0]['Title']
            lang = filtered_data[0]['Language']
            vtemp = f"(Id: {id}, Author: {aut}, Title: {tit}, lang:{lang})"
            vtemp = wrap_string_atpos(vtemp, "| ", 56)
        string_conditions = f"Conditions: {get_conditions_pretty(cond_total)}"
        string_conditions = wrap_string_atpos(string_conditions, "| ", 58)

        print(
            MENU_OPTIONS_TEMPLATE.format(
                search_conditions=string_conditions,
                books_found=len(filtered_data),
                unique_book_val=vtemp,
            )
        )
        opt_menu = input(
            'Select a option (press "q" to return to the main menu)?\n'
        )
        opt_menu = opt_menu.lower()

        if opt_menu == "1":  # Search in any string field
            cond_val = {"Authors": ""}, {"Title": ""}, {"OPERATOR": "or"}
            query_field(
                "Enter the author or title to search?\n", cond_val, True, True
            )

        elif opt_menu == "2":  # Search a ID
            cond_val = {"Text#": ""}, {"OPERATOR": "or"}
            query_field("Enter the ID to search?\n", cond_val, True, False)

        elif opt_menu == "3":  # Add a author condition
            if len(filtered_data) <= 1:
                pause(NO_ACTION)
            else:
                cond_val = {"Authors": ""}, {"OPERATOR": "or"}
                query_field(
                    "Enter the author to search?\n", cond_val, False, True
                )

        elif opt_menu == "4":  # Add a title condition
            if len(filtered_data) <= 1:
                pause(NO_ACTION)
            else:
                cond_val = {"Title": ""}, {"OPERATOR": "or"}
                query_field(
                    "Enter the title to search?\n", cond_val, False, True
                )

        elif opt_menu == "5":  # Add a language condition
            if len(filtered_data) <= 1:
                pause(NO_ACTION)
            else:
                cond_val = {"Language": ""}, {"OPERATOR": "or"}
                query_field(
                    "Enter the language to filter (en/es/fr/it)?\n",
                    cond_val,
                    False,
                    True,
                )

        elif opt_menu == "6":  # Reset all the conditions
            filtered_data = catalog_data  # Reset all the conditions...
            cond_total = []
            pause("All conditions reseted...")

        elif opt_menu == "7":  # Show results of filtered_data
            if len(cond_total) > 0:
                print_data(filtered_data)
                pause()
            else:
                pause("First select some conditions to show some result")

        elif opt_menu == "8":  # Send a ebook if there is 1 book selected
            if len(filtered_data) != 1:
                pause(NO_ACTION)
            else:
                email_to = input("Enter the email address of the destiny?\n")
                email_to = email_to.strip()
                if valid_email(email_to):
                    send_ebook_mailto(email_to, filtered_data[0]["Text#"])
                else:
                    pause(f"Error: Invalid email address: {email_to}")

        elif (
            opt_menu == "9"
        ):  # Show statistics of request saved in the worksheet
            show_request_statistics()

        elif opt_menu == "q":  # Exit
            break

        else:
            if opt_menu != "":
                pause(f'Error: Unknown option selected "{opt_menu}"')


def main():
    """
    Main function
    """
    show_menu()


if __name__ == "__main__":
    main()
