from utils import AES_Encrypt, enc, generate_captcha_key, verify_param
import json
import requests
import re
import time
import logging
import datetime
import random
from urllib3.exceptions import InsecureRequestWarning

def get_date(day_offset: int = 0) -> str:
    today = datetime.datetime.now().date()
    offset_day = today + datetime.timedelta(days=day_offset)
    return offset_day.strftime("%Y-%m-%d")

class reserve:
    def __init__(self, sleep_time=0.2, max_attempt=50, enable_slider=False, reserve_next_day=False):
        self.requests = requests.session()
        self.submit_msg = []
        self.sleep_time = sleep_time
        self.captcha_slider_sess = requests.session()
        self.captcha_token_get_sess = requests.session()
        self.login_url = "https://passport2.chaoxing.com/api/login?"
        self.url = "https://office.chaoxing.com/front/third/apps/seat/code?id={}&seatNum={}"
        self.submit_url = "https://office.chaoxing.com/data/apps/seat/submit?"
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "passport2.chaoxing.com",
            "User-Agent": "Mozilla/5.0"
        }
        self.max_attempt = max_attempt
        self.enable_slider = enable_slider
        self.reserve_next_day = reserve_next_day
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def _get_page_token(self, url: str, require_value: bool = False):
        resp = self.requests.get(url=url, verify=False)
        html = resp.content.decode("utf-8")

        # token: 'xxx' or "xxx"
        m_token = re.search(r"token\s*[:=]\s*'([^']+)'", html) or re.search(r'token\s*[:=]\s*"([^"]+)"', html)
        token = m_token.group(1) if m_token else ""

        # Hidden value used in new enc (name may vary; match broadly)
        value = ""
        if require_value:
            mv = re.search(r'<input[^>]*type=["\']hidden["\'][^>]*value=["\']([^"\']+)["\']', html)
            value = mv.group(1) if mv else ""

        if require_value and (not token or not value):
            logging.error("Page missing token or hidden value")
        return token, value

    def get_login_status(self):
        logging.info("login and page_token")
        self.requests.headers.update(self.headers)
        resp = self.requests.get(url="https://office.chaoxing.com/front/third/apps/seat/code?id=4219&seatNum=380")
        textresp = resp.text
        js_time_result = re.findall(r"\.next\(\)\.val\(\s*'(\d{2}:\d{2}:\d{2})'\)", textresp)
        try:
            direction = re.findall(r"朝向:([\u4e00-\u9fa5]*)</div>", textresp)
            state = re.findall(r"状态:([\u4e00-\u9fa5]*)</div>", textresp)
            building = re.findall(r"楼层:([\u4e00-\u9fa5]*)</div>", textresp)
            time1, time2 = js_time_result
            logging.info(f"state: {state}, direction: {direction}, building: {building}")
            logging.info(f"time: {time1}-{time2}")
        except Exception:
            logging.info("request too frequent or wrong credentials")
            return

    def login(self, username: str, password: str):
        self.requests.headers.update(self.headers)
        # Clear headers not needed for login
        for k in [
            "Accept", "Accept-Language", "Cache-Control", "Connection", "Content-Type",
            "Host", "Pragma", "Sec-Ch-Ua", "Sec-Ch-Ua-Mobile", "Sec-Ch-Ua-Platform",
            "Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site", "Upgrade-Insecure-Requests", "User-Agent"
        ]:
            self.requests.headers.pop(k, None)
        params = {
            "fid": -1,
            "uname": username,
            "password": password,
            "refer": "http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D4219%26seatNum%3D380",
            "t": True,
        }
        r = self.requests.post(url=self.login_url, params=params, verify=False)
        obj = r.json()
        if obj.get("status"):
            logging.info(f"User {username} login successfully")
            return True, ""
        logging.info("login failed, check username and password")
        logging.info(r.text)
        return False, obj.get("msg", "")

    def resolve_captcha(self) -> int:
        import numpy as np
        import cv2

        current_timestamp = int(time.time() * 1000)
        captcha_key, time_stamp = generate_captcha_key(current_timestamp)
        url = (
            "https://captcha-b.chaoxing.com/captcha/get/verification/image"
            f"?token={captcha_key}&timestamp={time_stamp}&captchaType=slide&version=2"
        )
        resp = self.captcha_slider_sess.get(url=url)
        html = resp.content.decode("utf-8")
        bg_img_url = re.findall(r'"bg":"(https.*?\.jpg)"', html)[0]
        tp_img_url = re.findall(r'"tp":"(https.*?\.png)"', html)[0]

        headers = {"Referer": "https://office.chaoxing.com/", "User-Agent": "Mozilla/5.0"}
        bgc = self.requests.get(bg_img_url, headers=headers)
        tpc = self.requests.get(tp_img_url, headers=headers)
        bg = bgc.content
        tp = tpc.content

        def cut_slide(xbytes):
            arr = np.frombuffer(xbytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            return img

        bg_img = cv2.imdecode(np.frombuffer(bg, np.uint8), cv2.IMREAD_COLOR)
        tp_img = cut_slide(tp)
        bg_edge = cv2.Canny(bg_img, 100, 200)
        tp_edge = cv2.Canny(tp_img, 100, 200)
        res = cv2.matchTemplate(
            cv2.cvtColor(bg_edge, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(tp_edge, cv2.COLOR_GRAY2BGR),
            cv2.TM_CCOEFF_NORMED,
        )
        _, _, _, max_loc = cv2.minMaxLoc(res)
        return max_loc[0]

    def submit(self, times, roomid, seatid_list, action: bool):
        for seat in seatid_list:
            suc = False
            attempts = self.max_attempt
            while not suc and attempts > 0:
                token, value = self._get_page_token(self.url.format(roomid, seat), require_value=True)
                logging.info(f"Get token: {token}")
                captcha = self.resolve_captcha() if self.enable_slider else ""
                logging.info(f"Captcha token {captcha}")
                suc = self.get_submit(
                    self.submit_url,
                    times=times,
                    token=token,
                    roomid=roomid,
                    seatid=seat,
                    captcha=captcha,
                    action=action,
                    value=value,
                )
                if suc:
                    return True
                time.sleep(self.sleep_time)
                attempts -= 1
        return False

    def get_submit(self, url, times, token, roomid, seatid, captcha="", action=False, value=""):
        delta_day = 1 if self.reserve_next_day else 0
        day = datetime.date.today() + datetime.timedelta(days=delta_day)
        if action:
            day = datetime.date.today() + datetime.timedelta(days=1 + delta_day)

        params = {
            "roomId": roomid,
            "startTime": times[0],
            "endTime": times[1],
            "day": str(day),
            "seatNum": seatid,
            "captcha": captcha,
            "token": token,
            "type": "1",
            "verifyData": "1",
        }
        logging.info(f"submit parameter {params}")

        # New enc using hidden value
        params["enc"] = verify_param(params, value)

        headers = {
            "Referer": f"https://office.chaoxing.com/front/apps/seat/select?id={roomid}&day={str(day)}",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0",
        }

        r = self.requests.post(url=url, params=params, headers=headers, verify=True)
        text = r.content.decode("utf-8")
        try:
            obj = json.loads(text)
        except Exception:
            obj = {"success": False, "raw": text}

        self.submit_msg.append(f"{times[0]}~{times[1]}: {obj}")
        logging.info(obj)
        return obj.get("success", False)

    def roomid(self, deptldEnc: str):
        api = "https://office.chaoxing.com/data/apps/seat/room/list?deptIdEnc="
        url = api + deptldEnc + "&_=" + str(round(time.time() * 1000))
        r = self.requests.get(url=url)
        logging.info(r.text)
