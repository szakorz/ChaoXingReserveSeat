from utils import AES_Encrypt, enc, generate_captcha_key, verify_param
import json
import requests
import re
import time
import logging
import datetime
from urllib3.exceptions import InsecureRequestWarning

def get_date(day_offset: int=0):
    today = datetime.datetime.now().date()
    offset_day = today + datetime.timedelta(days=day_offset)
    tomorrow = offset_day.strftime("%Y-%m-%d")
    return tomorrow

class reserve:
    def __init__(self, sleep_time=0.2, max_attempt=50, enable_slider=False, reserve_next_day=False):
        self.requests = requests.session()
        self.submit_msg = []
        self.sleep_time = 10
        self.captcha_slider_sess = requests.session()
        self.captcha_token_get_sess = requests.session()
        self.sleep_time = 0.2
        self.login_url = 'https://passport2.chaoxing.com/api/login?'
        self.url = 'https://office.chaoxing.com/front/third/apps/seat/code?id={}&seatNum={}'
        # self.url默认形成链接进入以获得token。若直接操作是submit_url
        self.submit_url = 'https://office.chaoxing.com/data/apps/seat/submit?'
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0....application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "passport2.chaoxing.com"
        }

        self.sleep_time = sleep_time
        self.max_attempt = max_attempt
        self.enable_slider = enable_slider
        self.reserve_next_day = reserve_next_day
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    
    # login and page token
    def _get_page_token(self, url, require_value=False):
        response = self.requests.get(url=url, verify=False)
        html = response.content.decode('utf-8')
        # 兼容新版：需要从页面拿 token 与隐藏的 value（用于 enc 算法）
        matches = re.findall(r"token = \'(.*?)\'", html)
        value_matches = re.findall(r'value="(.*?)"', html) if require_value else None
        if require_value:
            if not matches:
                logging.error(f"Failed to get token from {url}")
                return "", ""
            if not value_matches:
                logging.error(f"Failed to get submit value from {url}")
                return matches[0], ""
        return (matches[0] if matches else "", value_matches[0] if value_matches else "")

    def get_login_status(self):
        logging.info("======= login and page_token =======")
        headerss = self.requests.headers
        headerss.update(self.headers)
        self.requests.headers = headerss
        logging.info("Headers长这个样：")
        logging.info(self.requests.headers)
        resp = self.requests.get(url="https://office.chaoxing.com/front/third/apps/seat/code?id=4219&seatNum=380")
        textresp = resp.text
        js_time_regex = r"\.next\(\)\.val\([\s]*\'(\d{2}:\d{2}:\d{2})\'\)"
        js_time_result = re.findall(js_time_regex, textresp)
        try:
            direction = re.findall(r'朝向:([\u4e00-\u9fa5]*)</div>', textresp)
            state = re.findall(r'状态:([\u4e00-\u9fa5]*)</div>', textresp)
            building = re.findall(r'楼层:([\u4e00-\u9fa5]*)</div>', textresp)
            time1, time2 = js_time_result
            logging.info(f'======= state: {state}, direction{direction}, building{building} =======')
            logging.info(f'======= time is: {time1}-{time2} =======')
        except BaseException as e:
            logging.info("======= request less than frequency =======")
            logging.info("======= wrong password or username =======")
            return

    def login(self, username, password):
        headers = self.requests.headers
        headers.update(self.headers)
        self.requests.headers = headers
        inners = [
            "Accept","Accept-Language","Cache-Control","Connection","Content-Type",
            "Host","Pragma","Sec-Ch-Ua","Sec-Ch-Ua-Mobile","Sec-Ch-Ua-Platform",
            "Sec-Fetch-Dest","Sec-Fetch-Mode","Sec-Fetch-Site","Upgrade-Insecure-Requests","User-Agent"
        ]
        for item in inners:
            try:
                self.requests.headers.pop(item)
            except:
                pass
        parm = {
            "fid": -1,
            "uname": username,
            "password": password,
            "refer": "http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D4219%26seatNum%3D380",
            "t": True,
        }
        jsons = self.requests.post(url=self.login_url, params=parm, verify=False)
        obj = jsons.json()
        if obj["status"]:
            logging.info(f"User {username} login successfully")
            return (True, "")
        else:
            logging.info(
                f"User {username} login failed. Please check you password and username! "
            )
            logging.info(f'{jsons.text}')
            if 'ok' in jsons.text:
                logging.info('duolijieshao')
            # todo: duplicate login
            return (False, "密码错误：{re0}\n登录失败{obj['msg']}!")
    def get_weight_time(self, text):
        js_time_regex = r"\.next\(\)\.val\([\s]*\'(\d{2}:\d{2}:\d{2})\'\)"
        js_time_result = re.findall(js_time_regex, text)
        return js_time_result

    def resolve_captcha(self):
        import numpy as np
        import cv2

        #0. 请求体构建过程：使用和真实发起请求一致的请求方式
        #1. 获得验证码键值。尚不明其原理CDN。
        current_timestamp = int(time.time() * 1000)
        captcha_key, time_stamp = generate_captcha_key(current_timestamp)
        url = f'https://captcha-b.chaoxing.com/captcha/get/verification/image?token={captcha_key}&timestamp={time_stamp}&captchaType=slide&version=2'
        #2. 从b服务拿两个资源。图片和模板。必须以b开头。不是固定的。服务的响应会提示接入哪个服务。服务端会推出多个服务以应对不同的学校场景。不一定是b开头
        response = self.captcha_slider_sess.get(url=url)
        html = response.content.decode("utf-8")
        bg_img_url = re.findall(r'"bg":"(https.*\.jpg)"', html)[0]
        tp_img_url = re.findall(r'"tp":"(https.*\.png)"', html)[0]
        logging.info(f'请求滑块验证的图像：{bg_img_url, tp_img_url}')
        #3. 获取图片本体，并以适配知乎的Web方式，并且将移动端属性全部去掉，避免出现移动端差异化的问题
        bg, tp = bg_img_url, tp_img_url
        #4. API调用样例（以下基本照抄知乎的api），去生成一个猜测值。猜测值必须在c端生成。知乎那边是强制使用js来构建query字符串，这里是使用python生成query字符串。
        #5. 送入local方法生成encrypted_method
        motionArg = {
            "x": random.randint(140, 160),
            "y": random.randint(5, 10),
            "t": random.randint(800, 1200)
        }
        def cut_slide(x):
            import numpy as np
            import cv2
            tpp  = np.frombuffer(x, np.uint8)
            asd = cv2.imdecode(tpp, cv2.IMREAD_GRAYSCALE)
            coords = np.column_stack(np.where(asd==255)) 
            chess = coords[0][1]
            join  = cv2.imencode('.png',asd)[1].tobytes()
            join2 = np.where(asd==255)[0][0]
            return asd

        def encrypt(param, token):
            return AES_Encrypt(str(param)+token)

        def get_sign(param: dict, token):
            return encrypt(param, token)

        token_url = 'https://captcha-b.chaoxing.com/captcha/get/verification/sign'
        param = {
            "motionData": motionArg,
            "cty": "slide",
            "captchaType": "slide",
            "version": "2"
        }
        sign_token = self.captcha_token_get_sess.post(url=token_url, json=param).json().get('token')
        sign = get_sign(param, sign_token)
        # debug_sign = self.captcha_token_get_sess.post(url=token_url, json=param).json()
        #5. 使用api模拟的话，此处不能继续使用我们的api了，API包含了UA识别，只是放在了一个个接入的人身上。必须使用爬虫适应知乎识别
        bg = bg_img_url
        tp = tp_img_url
        c_captcha_headers = {
            "Referer": "https://office.chaoxing.com/",
            "Host": "captcha-b.chaoxing.com",
            "Pragma" : 'no-cache',
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'Sec-Ch-Ua-Mobile':'?0',
            'Sec-Ch-Ua-Platform':'"Linux"',
            'Sec-Fetch-Dest':'document',
            'Sec-Fetch-Mode':'navigate',
            'Sec-Fetch-Site':'none',
            'Sec-Fetch-User':'?1',
            'Upgrade-Insecure-Requests':'1',
            'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleW...ebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        bgc, tpc = self.requests。get(bg, headers=c_captcha_headers), self.requests。get(tp, headers=c_captcha_headers)
        bg, tp = bgc.content, tpc.content 
        bg_img = cv2.imdecode(np.frombuffer(bg, np.uint8), cv2.IMREAD_COLOR)  
        tp_img = cut_slide(tp)
        bg_edge = cv2.Canny(bg_img, 100, 200)
        tp_edge = cv2.Canny(tp_img, 100， 200)
        bg_pic = cv2.cvtColor(bg_edge, cv2.COLOR_GRAY2RGB)
        tp_pic = cv2.cvtColor(tp_edge, cv2.COLOR_GRAY2RGB)
        res = cv2.matchTemplate(bg_pic, tp_pic, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(res)  
        tl = max_loc
        return tl[0]

    def submit(self, times, roomid, seatid, action):
        for seat 在 seatid:
            suc = False
            while ~suc 和 self.max_attempt > 0:
                token, value = self._get_page_token(self.url.format(roomid, seat), require_value=True)
                logging.info(f"Get token: {token}")
                captcha = self.resolve_captcha() if self.enable_slider else ""
                logging.info(f"Captcha token {captcha}")
                suc = self.get_submit(
                    self.submit_url，
                    times=times,
                    token=token,
                    roomid=roomid,
                    seatid=seat,
                    captcha=captcha,
                    action=action,
                    value=value
                )
                if suc:
                    return suc
                time.sleep(self.sleep_time)
                self.max_attempt -= 1
        return suc

    def get_submit(self, url, times, token, roomid, seatid, captcha="", action=False, value=""):
        delta_day = 1 if self.reserve_next_day else 0
        day = datetime.date。today() + datetime.timedelta(days=0+delta_day)  # 预约今天，修改days=1表示预约明天
        if action:
            day = datetime.date。today() + datetime.timedelta(days=1+delta_day)  # 由于action时区问题导致其早+8区一天
        parm = {
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
        logging.info(f"submit parameter {parm} ")
        # 新版 enc 计算：按上游规则以页面隐藏 value 参与签名
        parm["enc"] = verify_param(parm, value)
        html = self.requests。post(
            url=url, params=parm, verify=True).content.decode('utf-8')
        self.submit_msg.append(
            times[0] + "~" + times[1] + ':  ' + str(json.loads(html)))
        logging.info(json.loads(html))
        return json.loads(html)["success"]

    def roomid(self, deptldEnc):
        get = 'https://office.chaoxing.com/data/apps/seat/room/list?deptIdEnc='
        freight = get+deptldEnc+'&_=' + str(round(time.time() * 1000))
        receives = self.requests.get(url=freight)
        logging.info(f'{receives.text}')
