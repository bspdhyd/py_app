#All database calls
import os
import atexit
import hashlib
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

from flask import Flask, session
import mysql.connector
from mysql.connector import Error
from mysql.connector import pooling
from datetime import datetime

class DatabaseManager:
    _instance = None

    def __init__(self):
        if DatabaseManager._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            DatabaseManager._instance = self
            
            # Read db config map from environment variables
            self.db_host = os.getenv('DB_HOST', '127.0.0.1')
            self.db_port = int(os.getenv('DB_PORT', 3306))
            self.db_user = os.getenv('DB_USER')
            self.db_password = os.getenv('DB_PASSWORD')
            self.db_name = os.getenv('DB_NAME')
            
            self.pool = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()
        return cls._instance

    def _initialize_pool(self):
        if self.pool is None:
            try:
                self.pool = pooling.MySQLConnectionPool(
                    pool_name="bspd_pool",
                    pool_size=10,
                    pool_reset_session=True,
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name
                )
            except Error as e:
                print(f"Error creating connection pool: {e}")
                raise

    def get_connection(self):
        self._initialize_pool()
        return self.pool.get_connection()

    def close(self):
        # Pool doesn't need explicit closing like the tunnel did, 
        # but we keep the method for consistency.
        pass

# Ensure the manager is cleaned up if needed (though pool handles itself mostly)
atexit.register(lambda: DatabaseManager.get_instance().close())

def create_connection():
    return DatabaseManager.get_instance().get_connection()

def run_fetchall_query(query, params):
    conn = create_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    finally:
        conn.close()

def run_fetchone_query(query, params):
    conn = create_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result
    finally:
        conn.close()

def run_crud_query(query, params):
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
    finally:
        conn.close()
    
def get_user_by_credentials(member_id, password):
    query = """SELECT MEMBER_ID, MEMBER_TYPE, Alias, Email_ID, Referrer_ID, Phone_Num, Password FROM BSPD_Member 
                      WHERE MEMBER_ID = %s AND Status = 'Active' """
    params = [member_id]   
    user = run_fetchone_query(query, params)
    
    if user:
        stored_password = user['Password']
        # Check if it's a werkzeug hash (contains colons or is significantly longer than MD5)
        if stored_password and (':' in stored_password or '$' in stored_password):
            if check_password_hash(stored_password, password):
                return user
        else:
            # Legacy MD5 check (usually 32 chars)
            if stored_password == hashlib.md5(password.encode()).hexdigest():
                # On successful legacy login, upgrade the password hash immediately
                update_user_password(member_id, password)
                return user
    return None

def get_member_data(member_id):
    query = """SELECT MEMBER_ID, MEMBER_TYPE, Name, Surname, Alias, Email_ID, Year_Of_Birth, Referrer_ID, Father_ID, Mother_ID, Spouse_ID, Phone_Num,
                    Gotram_ID, BloodGroup, Notes, Gender, Nakshatra, Pada, Status, DupIndicator, Address1, Address2, Location, City, State, PIN_or_ZIP, Country
                FROM BSPD_Member WHERE MEMBER_ID = %s """
    params = [member_id]   
    return run_fetchone_query(query, params)

def create_tokens(logid,ipaddress):
    created_on = datetime.now()
    query = "INSERT INTO bspd_tokens ( emp_uid, createdon, token) VALUES (%s, %s, %s)"
    params = [logid, created_on, ipaddress]
    return run_crud_query(query, params)

def get_events():
    query = "SELECT * FROM BSPD_Event ORDER BY Event_date DESC LIMIT 10"
    params = []
    return run_fetchall_query(query, params)
    
def get_future_events():
    query = "SELECT * FROM BSPD_Event where Event_Status = '0' ORDER BY Event_date"
    params = []
    return run_fetchall_query(query, params)

def create_event (event_id, entity_id, event_date, event_description, event_loc,event_notes):
    query = "INSERT INTO BSPD_Event (EVENT_ID, DEShCode, Event_date, Event_Description, Event_Location, Event_Notes) VALUES (%s, %s, %s, %s, %s, %s)"
    params = [event_id, entity_id, event_date, event_description, event_loc, event_notes]
    run_crud_query(query, params)
    
def get_event_by_id(event_id):
    query = "SELECT * FROM BSPD_Event WHERE EVENT_ID = %s"
    params = [event_id]
    return run_fetchone_query(query, params)

def update_event(event_id, entity_id, event_date, event_description, event_loc, event_notes, event_status):
    query = """UPDATE BSPD_Event
    SET Event_Description = %s, Event_Location = %s,
        Event_Notes = %s, Event_status = %s, Event_date = %s
    WHERE EVENT_ID = %s AND DEShCode = %s"""
    params = [event_description, event_loc, event_notes, event_status, event_date, event_id, entity_id]
    run_crud_query(query, params)
    
def delete_event(event_id, entity_id):
    query = "DELETE FROM BSPD_Event WHERE EVENT_ID = %s AND DEShCode = %s"
    params = [event_id, entity_id]
    run_crud_query(query, params)
    
def get_att_reg_event(event_id, entity_id):
    query = "Select * from BSPD_Event_Registration  Where EVENT_ID = %s and DEShCode = %s ORDER by UpdatedDate DESC"
    params = [event_id, entity_id]
    return run_fetchall_query(query, params)
    
def get_attendcount_event(event_id):
    query = """ SELECT COUNT(*) AS total_attended FROM BSPD_Event_Registration
            WHERE EVENT_ID = %s AND Attended = 'Y' """
    params = [event_id]
    return run_fetchone_query(query, params)   
    
def create_attendence(event_id, entity_id, member_id, registered, attended):
    memid = session['user']['MEMBER_ID']
    query = """INSERT INTO BSPD_Event_Registration (EVENT_ID, DEShCode, MEMBER_ID, Registered, Attended, CreatedBy, UpdatedBy)
                VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE Attended = %s, UpdatedBy = %s"""
    params = [event_id, entity_id, member_id, registered, attended, memid, memid, attended, memid]
    run_crud_query(query, params)
    
def create_registration(event_id, member_id, registered, eventrole):
    crid = session['user']['MEMBER_ID']
    entity_id = session['entity_id']
    query = """INSERT INTO BSPD_Event_Registration 
        (EVENT_ID, MEMBER_ID, Registered, PrimaryRole, CreatedBy, DEShCode, UpdatedBy)
        VALUES (%s, %s, %s, %s, %s, %s, %s) """
    params = [event_id, member_id, registered, eventrole, crid, entity_id, crid]
    run_crud_query(query, params)
    
def update_registration(event_id, member_id, registered, role):
    updid = session['user']['MEMBER_ID']
    query = """UPDATE BSPD_Event_Registration SET Registered = %s, PrimaryRole = %s, UpdatedBy = %s
        WHERE EVENT_ID = %s AND MEMBER_ID = %s """
    params = [registered, role, updid, event_id, member_id]
    run_crud_query(query, params)
    
def get_all_registrations():
    query = """ SELECT * FROM BSPD_Event_Registration
        ORDER BY UpdatedDate DESC LIMIT 10 """
    params = []
    return run_fetchall_query(query, params)
    
def search_members(criteria):
    search = criteria.strip()
    value = f"%{search}%"
    query = """ SELECT m.MEMBER_ID, m.Surname, m.Alias, m.Year_Of_Birth, m.Email_ID,
                    m.Gotram_ID, g.Gotra, m.Phone_Num, m.DupIndicator
            FROM BSPD_Member m JOIN BSPD_Pravara_Gotra g ON m.Gotram_ID = g.PG_ID
            WHERE m.MEMBER_ID LIKE %s OR m.Phone_Num LIKE %s OR m.Surname LIKE %s 
               OR m.Name LIKE %s OR m.Email_ID LIKE %s OR g.Gotra LIKE %s 
            ORDER BY m.Year_Of_Birth """
    params = [value, value, value, value, value, value]
    return run_fetchall_query(query, params)

def create_expense(event_id, voucher_num, payee_id, amount, amount_details, expense_type):
    query = """ INSERT INTO BSPD_Expenses (EVENT_ID, Voucher_Num, PAYEE_ID, Amount, Amount_Details, Expense_Type, DEShCode)
        VALUES (%s, %s, %s, %s, %s, %s, %s) """
    params = [event_id, voucher_num, payee_id, amount, amount_details, expense_type, 'BHBNR001']
    run_crud_query(query, params)
    
def update_expense(amount, amount_details, expense_type, voucher_num, trn_id):
    query = """ UPDATE BSPD_Expenses
        SET Amount=%s, Amount_Details=%s, Expense_Type=%s, Voucher_Num=%s
        WHERE TRN_ID=%s """
    params = [amount, amount_details, expense_type, voucher_num, trn_id]
    run_crud_query(query, params)
    
def delete_expense(trn_id):
    query = "DELETE FROM BSPD_Expenses WHERE TRN_ID=%s"
    params = [trn_id]
    run_crud_query(query, params)
    
def get_expenses_by_event_id(event_id):
    query = "SELECT * FROM BSPD_Expenses WHERE EVENT_ID = %s ORDER BY TRN_ID DESC"
    params = [event_id]
    return run_fetchall_query(query, params)
    
def get_all_expenses():
    query = "SELECT * FROM BSPD_Expenses ORDER BY TRN_ID DESC LIMIT 5"
    params = []
    return run_fetchall_query(query, params)
    
def create_contribution(member_id, event_id, amount, contribution_type, contribution_date, reference_details, receipt_pdf_url, deshcode='BHBNR001'):
    query = """ INSERT INTO BSPD_Member_Contribution 
                (Member_id, EVENT_ID, Amount, Contribution_Type, Contribution_Date, Reference_Details, Receipt_PDF_URL, DEShCode, Approved)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'N') """
    params = [member_id, event_id, amount, contribution_type, contribution_date, reference_details, receipt_pdf_url, deshcode]
    run_crud_query(query, params)
    
def update_contribution(amount, contribution_type, reference_details, approved, receipt_pdf_url, member_id, event_id):
    query = """ UPDATE BSPD_Member_Contribution
        SET Amount=%s, Contribution_Type=%s, Reference_Details=%s, Approved=%s, Receipt_PDF_URL=%s
        WHERE Member_id=%s AND EVENT_ID=%s """
    params = [amount, contribution_type, reference_details, approved, receipt_pdf_url, member_id, event_id]
    run_crud_query(query, params)
    
def get_all_contributions():
    query = "SELECT * FROM BSPD_Member_Contribution ORDER BY Contribution_Date DESC LIMIT 10"
    params = []
    return run_fetchall_query(query, params)
    
def get_contributions_by_member_or_event(search_value):
    query = """ SELECT * FROM BSPD_Member_Contribution
        WHERE Member_id = %s OR EVENT_ID = %s
        ORDER BY Contribution_Date DESC """
    params = [search_value, search_value]
    return run_fetchall_query(query, params)
    
def delete_contribution(member_id, event_id):
    query = """ DELETE FROM BSPD_Member_Contribution
        WHERE Member_id = %s AND EVENT_ID = %s """
    params = [member_id, event_id]
    run_crud_query(query, params)
    
def get_contribution_report(member_id=None, event_id=None):
    query = """ SELECT MEMBER_ID, EVENT_ID, Amount, Contribution_Type, Reference_Details, Transaction_Code
        FROM BSPD_View_Contribution_Report
        WHERE 1=1 """
    params = []
    if member_id:
        query += " AND MEMBER_ID = %s"
        params.append(member_id)
    if event_id:
        query += " AND EVENT_ID = %s"
        params.append(event_id)
    return run_fetchall_query(query, params)
    
def get_expenses_report(member_id=None, event_id=None):
    query = """ SELECT TRN_ID, EVENT_ID, TRN_DATE, Voucher_Num, Amount, Amount_Details
        FROM BSPD_Expenses
        WHERE 1=1 """
    params = []
    if member_id:
        query += " AND PAYEE_ID = %s"
        params.append(member_id)
    if event_id:
        query += " AND EVENT_ID = %s"
        params.append(event_id)
    return run_fetchall_query(query, params)
    
def get_attendance_report(member_id=None, event_id=None):
    query = """SELECT bm.Alias as RegisteredMember, (year(SYSDATE()) - bm.Year_Of_Birth) as Age, ifnull(ber.Attended ,'-') as Attendance,
 ber.PrimaryRole as PrimaryRole,  bm2.Alias as RegisteredBy, date(ber.CreatedDate ) as RegisteredDate
   FROM BSPD_Event_Registration ber, 
        BSPD_Member bm,
        BSPD_Member bm2 
  WHERE  ber.MEMBER_ID =bm.MEMBER_ID 
   AND ber.CreatedBy =bm2.MEMBER_ID"""
    
    params = []
    if member_id:
        query += " AND MEMBER_ID = %s"
        params.append(member_id)
    if event_id:
        query += " AND EVENT_ID = %s"
        params.append(event_id)
    query += " ORDER BY PrimaryRole ASC"

    return run_fetchall_query(query, params)
    
def get_recognition_report(member_id=None, event_id=None):
    query = """ SELECT EVENT_ID, BSPD_Member_ID, Sub_Category_ID, Notes
        FROM BSPD_Event_Recognition
        WHERE 1=1 """
    params = []
    if member_id:
        query += " AND BSPD_Member_ID = %s"
        params.append(member_id)
    if event_id:
        query += " AND EVENT_ID = %s"
        params.append(event_id)
    return run_fetchall_query(query, params)
    
def get_registration_report(member_id=None, event_id=None):
    query = """ SELECT r.EVENT_ID, m.Alias, m.Phone_num, r.PrimaryRole
        FROM BSPD_Event_Registration r JOIN BSPD_Member m 
        ON r.MEMBER_ID = m.MEMBER_ID WHERE r.EVENT_ID = %s """
    params = [event_id]
    return run_fetchall_query(query, params)
    
def get_references_report(member_id):
    query = """ SELECT MEMBER_ID, Surname, Name, Gender, Year_Of_Birth
        FROM BSPD_Member WHERE Referrer_ID = %s """
    params = [member_id]
    return run_fetchall_query(query, params)

def get_lstmembers():
    query = "SELECT MEMBER_ID, Alias from BSPD_Member order by MEMBER_ID DESC LIMIT 10"
    params = []
    return run_fetchall_query(query, params)

def get_gotras():
    query = "SELECT * from BSPD_Pravara_Gotra where PG_ID > 0 order by Gotra"
    params = []
    return run_fetchall_query(query, params)

def create_member(surname, name, gender, year_of_birth, gotram_id, email, phone_num, referrer, bloodgroup, notes, addloc, addline1, addline2, addcity, addstate, addpin, addcntry):
    memid = session['user']['MEMBER_ID']
    # Hash the initial password (defaulting to phone number)
    hashed_password = generate_password_hash(phone_num, method='pbkdf2:sha256', salt_length=16)

    query = """ INSERT INTO BSPD_Member 
        ( Surname, Name, Gender, Year_Of_Birth, Gotram_ID, Email_ID, Phone_Num, Referrer_ID, Location, Address1, Address2, City, State, PIN_or_ZIP, Country, BloodGroup, Password, Created_By, Updated_By, Notes) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
    params = [surname, name, gender, year_of_birth, gotram_id, email, phone_num, referrer, addloc, addline1, addline2, addcity, addstate, addpin, addcntry, bloodgroup, hashed_password, memid, memid, notes]
    run_crud_query(query, params)

def check_dup_member(surname, gender, yob, gotramid, email, phonenum):
    query = """SELECT Alias from BSPD_Member 
                where Surname = %s and Gender = %s and Year_Of_Birth = %s and Gotram_ID = %s and Email_ID = %s and Phone_Num = %s """
    params = [surname, gender, yob, gotramid, email, phonenum]
    print("YOB :",query)
    print("Params :",params)
    return run_fetchone_query(query, params)

def get_podili_assignment(year_of_birth=None, alias=None, assigned_status='all'):
    current_year = datetime.now().year
    max_year = current_year - 9
    min_year = current_year - 17

    query = """ SELECT m.MEMBER_ID, m.Alias, m.Surname, m.Year_Of_Birth,m.Phone_Num,
                m.Mother_ID, m.Father_ID, m.Notes, c.Assigned_MemID, CONCAT(a.Name, ' ', a.Surname) AS Assigned_Name
                FROM BSPD_Member m LEFT JOIN BSPD_College_Admission c ON m.MEMBER_ID = c.Student_MemID
                    LEFT JOIN BSPD_Member a ON c.Assigned_MemID = a.MEMBER_ID
                WHERE m.Gender = 'M' AND m.Status = "Active" AND m.Year_Of_Birth BETWEEN %s AND %s """
    params = [min_year, max_year]

    if year_of_birth is not None:
        query += " AND m.Year_Of_Birth = %s"
        params.append(year_of_birth)

    if alias:
        query += " AND (LOWER(m.Alias) LIKE %s OR CAST(m.MEMBER_ID AS CHAR) LIKE %s)"
        alias_param = f"%{alias.lower()}%"
        params.extend([alias_param, alias_param])
    
    if assigned_status == 'pending':
        query += " AND (c.Assigned_MemID IS NULL)"
    elif assigned_status == 'assigned':
        query += " AND (c.Assigned_MemID IS NOT NULL)"

    query += " ORDER BY m.Phone_Num ASC"

    return run_fetchall_query(query, params)


def update_notes_and_assigned(member_id, notes, assigned_memid):
    memid = session['user']['MEMBER_ID']
    # Update Notes in BSPD_Member
    query_notes = " UPDATE BSPD_Member SET Notes = %s WHERE MEMBER_ID = %s "
    params_notes = (notes, member_id)
    run_crud_query(query_notes, params_notes)

    # Insert or update Assigned_MemID in BSPD_College_Admission
    query = """ INSERT INTO BSPD_College_Admission (Student_MemID, Assigned_MemID, Created_By, Updated_By)
        VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE Assigned_MemID = %s, Updated_By = %s """
    params = (member_id, assigned_memid, memid, memid, assigned_memid, memid)
    run_crud_query(query, params)
    

def get_college_admissions():
    query = """ SELECT c.Student_MemID, m.Alias, m.Phone_Num, c.Onboard_Status,
            c.Assigned_MemID, c.Assignee_Notes, c.Admission_Num, c.Admission_Dt
        FROM BSPD_College_Admission c LEFT JOIN BSPD_Member m ON c.Student_MemID = m.MEMBER_ID """
    results = run_fetchall_query(query, params=())
    return results

def update_college_admission(student_memid, admission_dt, assignee_notes, onboard_status, admission_num, updated_by):
    query = """ UPDATE BSPD_College_Admission
        SET Admission_Dt = %s, Assignee_Notes = %s, Onboard_Status = %s,
            Admission_Num = %s, Updated_By = %s
        WHERE Student_MemID = %s """
    updated_dt = datetime.now()
    params = (admission_dt, assignee_notes, onboard_status, admission_num, updated_by, student_memid)
    run_crud_query(query, params)
    
    
def search_college_admissions(alias=None, year_of_birth=None, status=None):
    query = """ SELECT c.Student_MemID, m.Alias, m.Phone_Num, m.Father_ID, m.Mother_ID, c.Onboard_Status, 
            c.Assigned_MemID, c.Assignee_Notes, c.Admission_Num, c.Admission_Dt, m.Year_Of_Birth
        FROM BSPD_College_Admission c LEFT JOIN BSPD_Member m ON c.Student_MemID = m.MEMBER_ID
        WHERE 1=1 """

    params = []
    if alias:
        query += " AND m.Alias LIKE %s"
        params.append(f"%{alias}%")

    if year_of_birth:
        query += " AND m.Year_Of_Birth = %s"
        params.append(year_of_birth)

    if status:
        query += " AND c.Onboard_Status = %s"
        params.append(status)

    results = run_fetchall_query(query, params)
    return results
    
def update_user_password(member_id, new_password):
    hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=16)
    query = "UPDATE BSPD_Member SET Password = %s WHERE MEMBER_ID = %s"
    params = [hashed_password, member_id]
    run_crud_query(query, params)

def get_all_children(member_id):
    query = "SELECT MEMBER_ID FROM BSPD_Member WHERE Father_ID = %s OR Mother_ID = %s ORDER BY Year_Of_Birth"
    params = [member_id, member_id]
    return run_fetchall_query(query, params)
    
def get_expenses_by_event(event_id):
    query = """ SELECT Category AS Category_ID, SUM(Amount) AS TotalAmount FROM BSPD_View_Expense_Report
                WHERE EVENT_ID = %s GROUP BY Category ORDER BY Category """
    params = [event_id]
    return run_fetchall_query(query, params)
    
def get_registrations_by_event(event_id):
    query = """ SELECT PrimaryRole AS Role, count(MEMBER_ID) AS TotalRgns FROM BSPD_Event_Registration
                WHERE EVENT_ID = %s and DEShCode = 'BHBNR001' GROUP BY PrimaryRole ORDER BY PrimaryRole """
    params = [event_id]
    return run_fetchall_query(query, params)

def get_contributions_by_event(event_id):
    query = """ SELECT Contribution_Type, SUM(Amount) AS TotalAmount FROM BSPD_View_Contribution_Report
                WHERE EVENT_ID = %s GROUP BY Contribution_Type ORDER BY Contribution_Type """
    params = [event_id]
    return run_fetchall_query(query, params)
    
def get_access_by_member(member_id):
    query = "SELECT * FROM BSPD_Member_Access WHERE Member_ID = %s"
    params = [member_id]
    return run_fetchone_query(query, params)

def update_member_access(member_id, event_value, membercu_value):
    query = """ INSERT INTO BSPD_Member_Access (Member_ID, Event, Member_CU)
                VALUES (%s, %s, %s) ON DUPLICATE KEY
                UPDATE Event = %s, Member_CU = %s """
    params =[member_id, event_value, membercu_value, event_value, membercu_value]
    run_crud_query(query, params)

def get_payee_details(member_id):
    query = "SELECT * FROM BSPD_View_Payee_List where MEMBER_ID = %s"
    params = [member_id]
    return run_fetchone_query(query, params)
    
    
def get_all_payee_details():
    query = """ SELECT Payee_ID, Name, MEMBER_ID, Govt_ID, Govt_ID_Num, Aadhar_Img_URL, Email_ID FROM BSPD_Payee """
    params = []
    return run_fetchall_query(query, params)
    
def get_all_vaidika_details():
    query = "SELECT * FROM BSPD_Vaidika_List WHERE Account_status = %s"
    params = ['Active']
    return run_fetchall_query(query, params)
    
def get_all_pravara_gotra():
    query = "SELECT PG_ID, Gotra, Risheya, Pravara FROM BSPD_Pravara_Gotra"
    params = []
    return run_fetchall_query(query, params)

def get_pending_expenses():
    query = "SELECT * FROM BSPD_View_Pending_Expenses"
    params = []
    return run_fetchall_query(query, params)

def get_transaction_code_master():
    query = """ SELECT Categroy_Type, Category_ID, Category_Desc, Sub_Category_ID, Sub_Category_Desc
                FROM BSPD_Transaction_Code_Master Order by Categroy_Type ASC, Category_ID ASC """
    params = []
    return run_fetchall_query(query, params)

def update_transaction_code_description(category_type, category_id, sub_category_id, category_desc, sub_category_desc):
    query = """
        UPDATE BSPD_Transaction_Code_Master 
        SET Category_Desc = %s, Sub_Category_Desc = %s, UpdatedDt = NOW()
        WHERE Categroy_Type = %s AND Category_ID = %s AND Sub_Category_ID = %s
    """
    params = [category_desc, sub_category_desc, category_type, category_id, sub_category_id]
    return run_query(query, params)
    
def update_member_by_id(member_id, first_name, last_name, gender, dupindicator, phone_num, gotram_id, Father_id, Mother_id, Spouse_id, YOB, nakshatra_id, Pada, Email_ID, notes, address1, address2, location, city, state, zipcode, country, status):
    upd_memid = session['user']['MEMBER_ID']
    query = """ UPDATE BSPD_Member SET Name = %s, Surname = %s, Gender = %s, DupIndicator = %s, Phone_Num = %s, Gotram_ID = %s, Father_ID = %s, Mother_ID = %s, Spouse_ID = %s, Year_Of_Birth = %s, Nakshatra = %s, Pada = %s, Email_ID = %s, Notes = %s,  Address1 = %s, Address2 = %s, Location = %s, City = %s, State = %s, PIN_or_ZIP = %s, Country = %s, Status = %s, Updated_By = %s WHERE MEMBER_ID = %s """
    params = [ first_name, last_name, gender,  dupindicator, phone_num, gotram_id, Father_id, Mother_id, Spouse_id, YOB, nakshatra_id, Pada, Email_ID, notes, address1, address2, location, city, state, zipcode, country, status, upd_memid, member_id ]
    run_crud_query(query, params)
    
#def update_member_by_id(member_id, Member_Type, first_name, gender, phone_num, gotram_id, Father_id, Mother_id, Spouse_id, YOB, nakshatra_id, Pada, Email_ID, notes, address1, address2, location, city, state, zipcode, country):
    
#    query = """ UPDATE BSPD_Member SET Name = %s, MEMBER_TYPE = %s, Gender = %s, Phone_Num = %s, Gotram_ID = %s, Father_ID = %s, Mother_ID = %s, Spouse_ID = %s, Year_Of_Birth = %s, Nakshatra = %s, Pada = %s, Email_ID = %s, Notes = %s,  Address1 = %s, Address2 = %s, Location = %s, City = %s, State = %s, PIN_or_ZIP = %s, Country = %s WHERE MEMBER_ID = %s """
#    params = [ first_name, Member_Type, gender, phone_num, gotram_id, Father_id, Mother_id, Spouse_id, YOB, nakshatra_id, Pada, Email_ID, notes, address1, address2, location, city, state, zipcode, country, member_id ]
#    run_crud_query(query, params)

def get_nakshatras():
    query = "SELECT * from BSPD_Nakshatra where NID > 0 order by All_S_English"
    params = []
    return run_fetchall_query(query, params)

def get_member_privileges(member_id):
    query = """ SELECT Smarta_Purohit, Veda_Pandit FROM BSPD_Member_Privileges
                WHERE MEMBER_ID = %s """
    params = [member_id]
    return run_fetchone_query(query, params)

def update_member_privileges(member_id, smarta_purohit, veda_pandit):
    query = """ UPDATE BSPD_Member_Privileges SET Smarta_Purohit = %s, Veda_Pandit = %s
                WHERE MEMBER_ID = %s """
    params = [smarta_purohit, veda_pandit, member_id]
    run_crud_query(query, params)

def get_all_requests():
    query = "SELECT * FROM BSPD_Request ORDER BY 1 DESC"
    params = []
    return run_fetchall_query(query, params)
    
def insert_request(category, description, status):
    updated_ts = datetime.now()
    updated_by = session['user']['MEMBER_ID']
    query = """ INSERT INTO BSPD_Request (Req_MemberID, Req_Category, Description, Req_Status, Created_Timestamp, Updated_By, Updated_Timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s) """
    params = [updated_by, category, description, status, updated_ts, updated_by, updated_ts]
    run_crud_query(query, params)
    
def update_request(request_num, status, description, resolution, resolver_id):
    updated_ts = datetime.now()
    updated_by = session['user']['MEMBER_ID']
    query = """ UPDATE BSPD_Request SET Req_Status = %s, Description = %s, Req_Resolution = %s, Req_ResolverID = %s, Updated_By = %s, Updated_Timestamp = %s
                WHERE Request_Num = %s """
    params = [status, description, resolution, resolver_id, updated_by, updated_ts, request_num]
    run_crud_query(query, params)

def get_all_requests_filtered(req_member_id=None, category=None, status=None):
    query = "SELECT * FROM BSPD_Request WHERE 1=1"
    params = []

    if req_member_id:
        query += " AND Req_MemberID = %s"
        params.append(req_member_id)
    if category:
        query += " AND Req_Category = %s"
        params.append(category)
    if status:
        query += " AND Req_Status = %s"
        params.append(status)
    query += " ORDER BY 1 DESC"

    return run_fetchall_query(query, params)
    
def get_contributions_by_month_range(start_month, end_month):
    query = """ SELECT DATE_FORMAT(Event_date, '%Y-%m') AS Month, Contribution_Type AS Type, SUM(Amount) AS Amount FROM BSPD_View_Contribution_Report
                WHERE DATE_FORMAT(Event_date, '%Y-%m') BETWEEN %s AND %s GROUP BY Month, Type ORDER BY Month """
    params = [start_month, end_month]
    return run_fetchall_query(query, params)

def get_expenses_by_month_range(start_month, end_month):
    query = """ SELECT DATE_FORMAT(TRN_DATE, '%Y-%m') AS Month, Category AS Type, SUM(Amount) AS Amount FROM BSPD_View_Expense_Report
                WHERE DATE_FORMAT(TRN_DATE, '%Y-%m') BETWEEN %s AND %s GROUP BY Month, Type ORDER BY Month """
    params = [start_month, end_month]
    return run_fetchall_query(query, params)
    
def get_members_with_status_issues():
    query = """ SELECT MEMBER_ID, Year_Of_Birth, Surname, Name, Gender, Status, Referrer_ID FROM BSPD_Member 
                WHERE Status IN ('Expired', 'Inactive', 'Not valid') LIMIT 100 """
    params = []
    return run_fetchall_query(query, params)

def get_members_with_referrer_issues():
    query = """ SELECT MEMBER_ID, Surname, Name, Year_Of_Birth, Gender, Status, Referrer_ID FROM BSPD_Member 
                WHERE Referrer_ID = 0 LIMIT 100 """
    params = []
    return run_fetchall_query(query, params)

def get_members_with_birthyear_issues():
    query = """ SELECT MEMBER_ID, Surname, Name, Year_Of_Birth, Gender FROM BSPD_Member 
                WHERE Year_Of_Birth IN (1900, 1980) LIMIT 100 """
    params = []
    return run_fetchall_query(query, params)
    
def get_members_with_surname_issues():
    query = """ SELECT MEMBER_ID, Surname, Name, Gender, Year_Of_Birth FROM BSPD_Member 
                WHERE LENGTH(Surname) < 4 LIMIT 100 """
    params = []
    return run_fetchall_query(query, params)

def get_members_with_no_contributions():
    query = """ SELECT Alias, Year_Of_Birth, Gender FROM BSPD_Member 
                WHERE MEMBER_ID NOT IN (SELECT Member_ID FROM BSPD_View_Contribution_Report) ORDER BY Alias LIMIT 100 """
    params = []
    return run_fetchall_query(query, params)
    
def get_yob_issues(member_id):
    query = """ SELECT Alias, Email_ID, Year_Of_Birth FROM BSPD_Member 
                WHERE Referrer_ID = %s AND Year_Of_Birth IN (1900, 1980) ORDER BY Alias """
    params = [member_id]
    return run_fetchall_query(query, params)

def get_surname_issues(member_id):
    query = """ SELECT Alias, Email_ID, Surname FROM BSPD_Member 
                WHERE Referrer_ID = %s AND LENGTH(Surname) < 4 ORDER BY Alias """
    params = [member_id]
    return run_fetchall_query(query, params)

def get_address_issues(member_id):
    query = """ SELECT Alias, Email_ID, Address1, Address2, Pin_Or_Zip FROM BSPD_Member 
                WHERE Referrer_ID = %s AND Pin_Or_Zip IS NULL ORDER BY Alias """
    params = [member_id]
    return run_fetchall_query(query, params)

def get_parent_issues(member_id):
    query = """ SELECT Alias, Email_ID, Father_ID, Mother_ID, Spouse_ID FROM BSPD_Member 
                WHERE Referrer_ID = %s AND (Father_ID = '0' OR Mother_ID = '0') ORDER BY Alias """
    params = [member_id]
    return run_fetchall_query(query, params)

def get_duplicate_issues(member_id):
    query = """ SELECT MEMBER_ID, Alias, Email_ID, DupIndicator FROM BSPD_Member 
                WHERE Referrer_ID = %s AND DupIndicator > 0 ORDER BY Email_ID """
    params = [member_id]
    return run_fetchall_query(query, params)

def upload_member_image(member_id, image_data):
    query = "UPDATE BSPD_Member SET MemImage = %s WHERE MEMBER_ID = %s"
    params = [image_data, member_id]
    run_crud_query(query, params)
    return True

def fetch_member_image(member_id):
    query = "SELECT MemImage FROM BSPD_Member WHERE MEMBER_ID = %s"
    params = [member_id]
    result = run_fetchone_query(query, params)
    if result and result['MemImage']:
        return result['MemImage']
    return None

def upload_member_image(member_id, image_data):
    query = "UPDATE BSPD_Member SET MemImage = %s WHERE MEMBER_ID = %s"
    params = [image_data, member_id]
    run_crud_query(query, params)
    return True

def get_receipt_data(transaction_code):
    query = """ SELECT Transaction_Code, Full_Name, BSPD_Member_id, Amount, Amount_In_Words, Contribution_Type, Event_Description, EVENT_ID, DEShCode, Event_Location,
                    Reference_Details, DATE_FORMAT(Contribution_Date, '%d-%b-%Y') AS Contribution_Date, DATE_FORMAT(Receipt_Date, '%d-%b-%Y') AS Receipt_Date
                FROM BSPD_View_Contribution_Report WHERE Transaction_Code = %s """
    params = [transaction_code]
    return run_fetchone_query(query, params)

def get_receipt_notes(slno):
    query = "SELECT Notes FROM BSPD_SIB_Collection_Report WHERE SLNO = %s"
    params = [slno]
    result = run_fetchone_query(query, params)
    return result['Notes'] if result else ""

def get_max_dup_indicator():
    query = "SELECT MAX(DupIndicator) AS Counter FROM BSPD_Member"
    params = []
    result = run_fetchone_query(query, params)
    return result['Counter'] if result and result['Counter'] else 0

def update_member_dup(member_id, surname, dup_num):
    new_surname = f"Flag* {surname}"
    query = """ UPDATE BSPD_Member
                SET DupIndicator = %s, Surname = %s
                WHERE MEMBER_ID = %s """
    params = [dup_num, new_surname, member_id]
    return run_crud_query(query, params)

def get_transaction_code_data(cattype, catid):
    query = """ SELECT * FROM BSPD_Transaction_Code_Master 
                WHERE Categroy_Type = %s and Category_ID = %s Order by  Sub_Category_ID ASC """
    params = [cattype, catid]
    return run_fetchall_query(query, params)

def insert_sib_collection_row(orgname, slno, id_value, name, tranid, trandate, tranamt, source):
    query = """ INSERT INTO BSPD_SIB_Collection_Report (ORGNAME, SLNO, ID, NAME, TRANID, TRANDATE, TRANAMT, SOURCE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
    params = [orgname, slno, id_value, name, tranid, trandate, tranamt, source]
    return run_crud_query(query, params)
    
def get_all_payees():
    query = "SELECT * FROM BSPD_Payee"
    params = []  
    return run_fetchall_query(query, params)
    
def insert_payee(data, file=None):
    query = """ INSERT INTO BSPD_Payee (Name, MEMBER_ID, Govt_ID, Govt_ID_Num, Purpose, Email_ID, Phone_Num, Address1, Address2, City, 
            State, Country, Aadhar_Img_URL, Govt_ID_Img, Created_By, created ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() ) """
    params = ( data['Name'], data['MEMBER_ID'], data['Govt_ID'], data['Govt_ID_Num'], data['Purpose'],
            data['Email_ID'], data['Phone_Num'], data['Address1'], data['Address2'], data['City'],
            data['State'], data['Country'], data['Aadhar_Img_URL'], file, data['Created_By'] )
    run_crud_query(query, params)

def update_payee(data, file=None):
    fields = [ 'Name', 'MEMBER_ID', 'Govt_ID', 'Govt_ID_Num', 'Purpose', 'Email_ID', 'Phone_Num',
        'Address1', 'Address2', 'City', 'State', 'Country', 'Aadhar_Img_URL', 'Updated_By' ]
    if file:
        fields.append('Govt_ID_Img')
    
    query = f""" UPDATE BSPD_Payee SET
            {', '.join(f"{field} = %s" for field in fields)},
            updated = NOW() WHERE Payee_ID = %s """
    params = tuple(data[field] for field in fields if field != 'Govt_ID_Img')
    if file:
        params += (file,)
    params += (data['Payee_ID'],)
    run_crud_query(query, params)

def search_payee(term):
    like_term = f"%{term}%"

    query = """ SELECT * FROM BSPD_Payee WHERE Payee_ID LIKE %s or MEMBER_ID like %s or Name LIKE %s """
    params = (like_term, like_term, like_term)
    return run_fetchall_query(query, params)

def get_member_by_id(member_id):
    query = """ SELECT MEMBER_ID, Name, Email_ID, Phone_Num, Address1, Address2, City, State, Country
        FROM BSPD_Member WHERE MEMBER_ID = %s """
    params = [member_id]
    return run_fetchone_query(query, params)
    
def get_all_payee_accounts():
    query = "SELECT * FROM BSPD_Payee_Account LIMIT 20"
    params = []  
    return run_fetchall_query(query, params)

def insert_payee_account(d):
    query = """INSERT INTO BSPD_Payee_Account 
               (Payee_ID, Payee_Acnt_Num, Name_In_Account, Nick_Name, Bank_Name, Branch, IFSC_CODE, Passbook_Img_URL, Bank_Registration_Code, Account_Status, Key_Notes, Account_Proof_Img, CreatedBy, CreatedDt)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())"""
    params = (
        d["Payee_ID"], d["Payee_Acnt_Num"], d["Name_In_Account"], d.get("Nick_Name"),
        d["Bank_Name"], d["Branch"], d["IFSC_CODE"], d.get("Passbook_Img_URL"),
        d["Bank_Registration_Code"], d["Account_Status"], d.get("Key_Notes"),
        d.get("Account_Proof_Img"), d["CreatedBy"]
    )
    return run_crud_query(query, params)

def update_payee_account(d):
    query = """UPDATE BSPD_Payee_Account SET
               Payee_Acnt_Num=%s, Name_In_Account=%s, Nick_Name=%s, Bank_Name=%s, Branch=%s,
               IFSC_CODE=%s, Passbook_Img_URL=%s, Bank_Registration_Code=%s, Account_Status=%s,
               Key_Notes=%s, Account_Proof_Img=%s
               WHERE Payee_ID=%s"""
    params = (
        d["Payee_Acnt_Num"], d["Name_In_Account"], d.get("Nick_Name"), d["Bank_Name"], d["Branch"],
        d["IFSC_CODE"], d.get("Passbook_Img_URL"), d["Bank_Registration_Code"], d["Account_Status"],
        d.get("Key_Notes"), d.get("Account_Proof_Img"), d["Payee_ID"]
    )
    return run_crud_query(query, params)

def search_payee_accounts(search_term):
    query = """
        SELECT * 
        FROM BSPD_Payee_Account
        WHERE Payee_ID = %s OR Nick_Name LIKE %s OR Name_In_Account LIKE %s
    """
    try:
        payee_id = int(search_term)
    except ValueError:
        payee_id = -1 

    params = (payee_id, f"%{search_term}%", f"%{search_term}%")
    return run_fetchall_query(query, params)

def get_payee_name_by_id(payee_id):
    query = "SELECT Name FROM BSPD_Payee WHERE Payee_ID = %s"
    params = [payee_id]
    result = run_fetchall_query(query, params)
    return result[0]["Name"] if result else None
    
def update_payment_confirmation(trn_id, utr_number, confirmation_id, payment_date):
    query = """
        UPDATE BSPD_Expenses
        SET 
            UTR_Number = %s,
            Payment_Confirmation_ID = %s,
            Payment_Date = %s,
            Payment_Status = 'paid'
        WHERE TRN_ID = %s
    """
    params = [utr_number, confirmation_id, payment_date, trn_id]
    run_crud_query(query, params)
    
def search_vmt_members(search_values):
    if not search_values:
        return []

    placeholders = ", ".join(["%s"] * len(search_values))
    query = f"""
        SELECT MEMBER_ID, Alias, Father_ID, Mother_ID, Spouse_ID, Referrer_ID
        FROM BSPD_Member
        WHERE MEMBER_ID IN ({placeholders})
          OR Alias IN ({placeholders})
        ORDER BY MEMBER_ID ASC
    """
    params = search_values + search_values
    return run_fetchall_query(query, params)

def update_vmt_member(member_id, father, mother, spouse, referrer):
    query = """
        UPDATE BSPD_Member
        SET Father_ID=%s, Mother_ID=%s, Spouse_ID=%s, Referrer_ID=%s
        WHERE MEMBER_ID=%s
    """
    run_crud_query(query, [father, mother, spouse, referrer, member_id])
    
def get_vmt_member_by_id(member_id):
    query = """
        SELECT MEMBER_ID, Alias, Father_ID, Mother_ID, Spouse_ID, Referrer_ID
        FROM BSPD_Member
        WHERE MEMBER_ID = %s
    """
    rows = run_fetchall_query(query, [member_id])
    return rows[0] if rows else None
    

def run_crud_query_lastid(query, params):
    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        last_id = cursor.lastrowid
        conn.commit()
        return last_id
    finally:
        db_manager.release_connection(conn)

def get_desh_codes():
    query = "SELECT DEShCode FROM BSPD_Dharmic_Entity ORDER BY DEShCode"
    return run_fetchall_query(query, [])

def get_open_events_for_contribution():
    query = "SELECT EVENT_ID FROM BSPD_Event WHERE Event_status = 0 ORDER BY EVENT_ID DESC"
    return run_fetchall_query(query, [])

def search_members_for_contribution(term):
    value = f"%{term}%"
    query = """SELECT Alias, Phone_Num, Email_ID, MEMBER_ID
               FROM BSPD_Member WHERE Status = 'Active'
               AND (Alias LIKE %s OR Phone_Num LIKE %s OR Email_ID LIKE %s)
               ORDER BY Alias LIMIT 20"""
    return run_fetchall_query(query, [value, value, value])

def create_manual_contribution(deshcode, event_id, member_id, amount, contribution_type,
                                contribution_date, reference_details, receipt_pdf_url, approved):
    created_by = session['user']['MEMBER_ID']
    query = """INSERT INTO BSPD_Member_Contribution
               (DEShCode, EVENT_ID, Member_id, Amount, Contribution_Type, Contribution_Date,
                Reference_Details, Receipt_PDF_URL, Approved, CreatedBy, UpdatedBy)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    params = [deshcode, event_id, member_id, amount, contribution_type, contribution_date,
              reference_details, receipt_pdf_url, approved, created_by, created_by]
    return run_crud_query_lastid(query, params)

def get_receipt_data(transaction_code):
    query = """SELECT Transaction_Code, Amt_In_Words FROM BSPD_Receipt_View
               WHERE Transaction_Code = %s"""
    return run_fetchone_query(query, [transaction_code])

def get_contributions_for_manual_update(deshcode=None, event_id=None, transaction_code=None,
                                         date_from=None, date_to=None):
    conditions = []
    params = []
    if deshcode:
        conditions.append("mc.DEShCode = %s")
        params.append(deshcode)
    if event_id:
        conditions.append("mc.EVENT_ID = %s")
        params.append(event_id)
    if transaction_code:
        conditions.append("mc.Transaction_Code = %s")
        params.append(transaction_code)
    if date_from:
        conditions.append("mc.Createdate >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("mc.Createdate <= %s")
        params.append(date_to)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"""SELECT mc.Transaction_Code, mc.DEShCode, mc.EVENT_ID, bm.Alias,
                       mc.Amount, mc.Contribution_Type, mc.Contribution_Date,
                       mc.Reference_Details, mc.Receipt_PDF_URL, mc.Approved, mc.Createdate
                FROM BSPD_Member_Contribution mc
                JOIN BSPD_Member bm ON mc.Member_id = bm.MEMBER_ID
                {where} ORDER BY mc.Transaction_Code DESC LIMIT 100"""
    return run_fetchall_query(query, params)

def update_manual_contribution(transaction_code, amount, contribution_type, contribution_date,
                                reference_details, receipt_pdf_url, approved):
    updated_by = session['user']['MEMBER_ID']
    query = """UPDATE BSPD_Member_Contribution
               SET Amount=%s, Contribution_Type=%s, Contribution_Date=%s,
                   Reference_Details=%s, Receipt_PDF_URL=%s, Approved=%s, UpdatedBy=%s
               WHERE Transaction_Code=%s"""
    run_crud_query(query, [amount, contribution_type, contribution_date,
                           reference_details, receipt_pdf_url, approved, updated_by, transaction_code])
