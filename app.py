from flask import Flask, jsonify, Response, make_response, request
import requests
import uuid
import base64
from bs4 import BeautifulSoup
import re
import html
from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)

schoolSessions = {}

searchKeys = {
    "udiseCode": "searchTypeOnSearchPage",
    "pinCode": "searchType",
    "name": ""
}

searchCodes = {
    "udiseCode": "2",
    "pinCode": "3",
    "name": "1"
}

@app.route("/api/v1/getCaptcha", methods=["GET"])
def getCaptcha():
    try:
        captcha_url = "https://src.udiseplus.gov.in/searchCaptcha"
        session = requests.Session()
        id = str(uuid.uuid4())

        response = session.get(captcha_url)
        captchaBase64 = base64.b64encode(response.content).decode("utf-8")

        # # For Testing Purpose only

        # imageString = f'<img src="data:image/png;base64,{captchaBase64}" alt="captcha">'
        # with open('captcha.html','w') as f:
        #     f.write(imageString)   
        #     f.close()

        # #

        schoolSessions[id] = {
            "session": session
        }

        json_response = {
            "sessionId": id,
            "image": "data:image/png;base64," + captchaBase64,
        }

        return jsonify(json_response)
    
    except Exception as e:
        print(e)
        return jsonify({"error": "Error in fetching captcha"})
    

@app.route("/api/v1/getSchools", methods=["POST"])
def getSchools():
    try:
        post_url = "https://src.udiseplus.gov.in/searchSchool/byUdiseCodeAndSchoolOnSearchPage"
        
        sessionId = request.json.get("sessionId")
        query = request.json.get("query")
        searchBy = request.json.get("searchBy")
        captcha = request.json.get("captcha")

        user = schoolSessions.get(sessionId)

        session = user['session']
        if session is None:
            return jsonify({"error": "Invalid session id"})
        
        postData = {
            "searchTypeOnSearchPage": searchCodes[searchBy],
            "udiseCode": query,
            "selectDropDown": "",
            # "searchTypeOnSearchPage": "",
            "captcha": captcha
        }

        response = session.post(post_url, data=postData)

        htmlString = response.text
        cleaned_html_string = htmlString.replace('\n', '').replace('\r', '').replace('\t', '').replace('\\', '')
        cleaned_html_string = html.unescape(cleaned_html_string)

        soup = BeautifulSoup(cleaned_html_string, 'html.parser')

        error = soup.find('div', id="invalidCaptchError").get_text().strip()

        if(error!=""):
            return jsonify({"error": "Invalid Captcha"})
        
        if("InValid Pin" in cleaned_html_string):
            return jsonify({"error": "Invalid PinCode"})
        
        if("InValid UDISE CODE" in cleaned_html_string):
            return jsonify({"error": "InValid UDISE CODE"})

        mainTable = soup.find('table', id="example")
        TRows = mainTable.find_all('tr')

        schools = []

        for i in range(1, len(TRows)):
            tds = TRows[i].find_all('td')

            UDISE_Code = tds[1].get_text().strip()
            schoolName = tds[2].get_text().strip()
            regionDetails = tds[3].get_text().strip().replace('District :', ' District :')
            basicDetails = tds[4].get_text().strip()

            pattern = re.compile(r"State Mgmt. :(.*?)NationalMgmt. :")
            stateMgmt = pattern.findall(basicDetails)[0].strip()
            
            pattern = re.compile(r"NationalMgmt. :(.*?)School Category :")
            nationalMgmt = pattern.findall(basicDetails)[0].strip()

            pattern = re.compile(r"School Category :(.*?)SchoolType :")
            schoolCategory = pattern.findall(basicDetails)[0].strip()

            pattern = re.compile(r"SchoolType :(.*?)PinCode :")
            schoolType = pattern.findall(basicDetails)[0].strip()

            pinCode = basicDetails[-6:]
            
            schoolStatus = tds[5].get_text().strip()

            schools.append({
                "udiseCode": UDISE_Code,
                "schoolName": schoolName,
                "regionDetails": regionDetails,
                "stateMgmt":stateMgmt,
                "nationalMgmt": nationalMgmt,
                "schoolCategory": schoolCategory,
                "schoolType": schoolType,
                "pinCode": pinCode,
                "schoolStatus": schoolStatus
            })

        data = {
            "numberOfSchools": len(TRows)-1,
            "schools": schools
        }
        
        return jsonify(data)
    
    except Exception as e:
        print(e)
        return jsonify({"error": "Error in fetching Schools"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(asgi_app, host='0.0.0.0', port=5001)
