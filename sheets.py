import os
import json
import gspread
from google.oauth2.service_account import Credentials
from config import SHEET_ID, SHEET_NAME, TESTING_SHEET


# ============================================
# GOOGLE CREDENTIALS
# Authenticates using service account from
# GOOGLE_CREDS environment variable.
# ============================================
def get_google_creds():
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    scopes     = ["https://www.googleapis.com/auth/spreadsheets"]
    return Credentials.from_service_account_info(creds_dict, scopes=scopes)


def get_sheets_client():
    return gspread.authorize(get_google_creds())


# ============================================
# GET BOTH WORKSHEETS
# Returns testing C2 sheet and Sheet1.
# ============================================
def get_worksheets():
    gc     = get_sheets_client()
    wb     = gc.open_by_key(SHEET_ID)
    sheet  = wb.worksheet(TESTING_SHEET)
    sheet1 = wb.worksheet(SHEET_NAME)
    return sheet, sheet1


# ============================================
# ENSURE HEADERS EXIST
# Creates header row if sheet is empty.
# ============================================
def ensure_testing_headers(sheet):
    rows = sheet.get_all_values()
    if len(rows) == 0:
        sheet.append_row([
            "Content ID", "Date & Time Posted", "C2 Text",
            "Reactions", "Comments", "Shares", "Post Link"
        ])
    return sheet.get_all_values()


def ensure_sheet1_headers(sheet1):
    rows = sheet1.get_all_values()
    if len(rows) == 0:
        sheet1.append_row([
            "Message ID", "Date & Time Added", "C2 Text",
            "Reactions", "Comments", "Shares", "Post Link"
        ])
    return sheet1.get_all_values()


# ============================================
# GET ALL IDS FROM A SHEET
# Returns a set of all IDs in column 1.
# ============================================
def get_all_ids(rows):
    ids = set()
    for row in rows[1:]:
        if row:
            ids.add(str(row[0]).strip())
    return ids


# ============================================
# SAVE POST TO TESTING C2
# Appends a new row with post data.
# ============================================
def save_to_testing(sheet, post_id, formatted_date, c2_text, reactions, comments, shares, post_link):
    sheet.append_row([
        post_id, formatted_date, c2_text,
        f"{reactions:,}", f"{comments:,}", f"{shares:,}", post_link
    ])


# ============================================
# SAVE WINNER TO SHEET1
# Appends a winning post to the A-RR database.
# ============================================
def save_to_sheet1(sheet1, post_id, posted_at, c2_text, reactions, comments, shares, post_link):
    sheet1.append_row([
        post_id, posted_at, c2_text,
        f"{reactions:,}", f"{comments:,}", f"{shares:,}", post_link
    ])


# ============================================
# UPDATE POST STATS IN A SHEET
# Updates reactions, comments, shares for a row.
# ============================================
def update_stats(sheet, row_index, reactions, comments, shares):
    sheet.update_cell(row_index, 4, f"{reactions:,}")
    sheet.update_cell(row_index, 5, f"{comments:,}")
    sheet.update_cell(row_index, 6, f"{shares:,}")


# ============================================
# UPDATE POST LINK IN A SHEET
# Updates the Post Link column for a row.
# ============================================
def update_post_link(sheet, row_index, post_link):
    sheet.update_cell(row_index, 7, post_link)


# ============================================
# DELETE ROWS BY POST IDS
# Reads sheet fresh then deletes matching rows
# from bottom up to preserve row numbers.
# ============================================
def delete_rows_by_ids(sheet, ids_to_delete):
    if not ids_to_delete:
        return
    rows           = sheet.get_all_values()
    rows_to_delete = []
    for i, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip() in ids_to_delete:
            rows_to_delete.append(i)
    for row_num in sorted(rows_to_delete, reverse=True):
        sheet.delete_rows(row_num)


# ============================================
# SAVE MANUAL INPUT TO SHEET1
# Used when user sends C2 via Telegram bot.
# ============================================
def save_manual_input(message_id, date_time, c2, likes):
    gc    = get_sheets_client()
    sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    rows  = sheet.get_all_values()

    if len(rows) == 0:
        sheet.append_row([
            "Message ID", "Date & Time Added", "C2 Text",
            "Reactions", "Comments", "Shares", "Post Link"
        ])
        rows = sheet.get_all_values()

    # Check duplicates by message ID
    for row in rows[1:]:
        if str(row[0]).strip() == message_id:
            return "duplicate"

    # Check duplicates by C2 text and likes
    for row in rows[1:]:
        if str(row[2]).strip() == c2 and str(row[3]).strip() == likes:
            return "duplicate"

    sheet.append_row([message_id, date_time, c2, likes, "", "", ""])
    return "saved"
