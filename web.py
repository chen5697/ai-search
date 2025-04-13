#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author   : CJ

import streamlit as st
import json
import os
import uuid
from streamlit_lottie import st_lottie
from streamlit_option_menu import option_menu
from streamlit_cookies_manager import EncryptedCookieManager
from login.utils import check_usr_pass
from login.utils import check_valid_name
from login.utils import check_valid_email
from login.utils import check_unique_email
from login.utils import check_unique_usr
from login.utils import register_new_usr
from login.utils import check_email_exists
from login.utils import generate_random_passwd
from login.utils import send_passwd_in_email
from login.utils import change_passwd
from login.utils import check_current_passwd
st.set_page_config(page_title="DMSearch_Demo",
                   page_icon="https://web.innodealing.com/dashboard/img/favicon/favicon.ico",
                   layout="wide")

from dm_search_demo import search_ui


class LoginPage:
    """
    Builds the UI for the Login/ Sign Up page.
    """

    def __init__(self, width=400, height=300,
                 hide_menu_bool: bool = False, hide_footer_bool: bool = False):
        """
        Arguments:
        -----------
        1. self
        2. auth_token : The unique authorization token received from - https://www.courier.com/email-api/
        3. company_name : This is the name of the person/ organization which will send the password reset email.
        4. width : Width of the animation on the login page.
        5. height : Height of the animation on the login page.
        6. logout_button_name : The logout button name.
        7. hide_menu_bool : Pass True if the streamlit menu should be hidden.
        8. hide_footer_bool : Pass True if the 'made with streamlit' footer should be hidden.
        9. lottie_url : The lottie animation you would like to use on the login page. Explore animations at - https://lottiefiles.com/featured
        """
        self.width = width
        self.height = height
        self.hide_menu_bool = hide_menu_bool
        self.hide_footer_bool = hide_footer_bool

        self.cookies = EncryptedCookieManager(
            prefix="streamlit_login_ui_yummy_cookies",
            password='9d68d6f2-4258-45c9-96eb-2d6bc74ddbb5-d8f49cab-edbb-404a-94d0-b25b1d4a564b')

        if not self.cookies.ready():
            st.stop()

    def check_auth_json_file_exists(self, auth_filename: str) -> bool:
        """
        Checks if the auth file (where the user info is stored) already exists.
        """
        file_names = []
        for path in os.listdir('./'):
            if os.path.isfile(os.path.join('./', path)):
                file_names.append(path)

        present_files = []
        for file_name in file_names:
            if auth_filename in file_name:
                present_files.append(file_name)

            present_files = sorted(present_files)
            if len(present_files) > 0:
                return True
        return False

    def login_widget(self) -> None:
        """
        Creates the login widget, checks and sets cookies, authenticates the users.
        """

        # Checks if cookie exists.
        if st.session_state['LOGGED_IN'] is False:
            if st.session_state['LOGOUT_BUTTON_HIT'] is False:
                fetched_cookies = self.cookies
                if '__login_signup_ui_username__' in fetched_cookies.keys():
                    if fetched_cookies['__login_signup_ui_username__'] != '':
                        st.session_state['LOGGED_IN'] = True

        if st.session_state['LOGGED_IN'] is False:
            st.session_state['LOGOUT_BUTTON_HIT'] = False

            del_login = st.empty()
            with del_login.form("登录"):
                username = st.text_input("昵称", placeholder='您唯一的用户名')
                password = st.text_input("密码", placeholder='您的密码', type='password')

                st.markdown("###")
                login_submit_button = st.form_submit_button(label='登录')

                if login_submit_button is True:
                    authenticate_user_check = check_usr_pass(username, password)

                    if authenticate_user_check is False:
                        st.error("无效的用户名或密码!")

                    else:
                        st.session_state.chat_history = []
                        st.session_state.session_id = uuid.uuid4()
                        st.session_state['LOGGED_IN'] = True
                        self.cookies['__login_signup_ui_username__'] = username
                        self.cookies.save()
                        del_login.empty()
                        st.rerun()

    def animation(self, animation_path) -> None:
        """
        Renders the lottie animation.
        """
        with open(animation_path, 'r') as lottie:
            lottie_json = json.load(lottie)
        st_lottie(lottie_json, width=self.width, height=self.height)

    def sign_up_widget(self) -> None:
        """
        Creates the sign-up widget and stores the user info in a secure way in the _secret_auth_.json file.
        """
        with st.form("注册"):
            name_sign_up = st.text_input("名字 *", placeholder='请输入您的名字【必须字母或_开头，只能包含字母、数字、_】')
            valid_name_check = check_valid_name(name_sign_up)

            email_sign_up = st.text_input("邮箱 *", placeholder='请输入您的邮箱')
            valid_email_check = check_valid_email(email_sign_up)
            unique_email_check = check_unique_email(email_sign_up)

            username_sign_up = st.text_input("昵称 *", placeholder='请输入唯一昵称')
            unique_username_check = check_unique_usr(username_sign_up)

            password_sign_up = st.text_input("密码 *", placeholder='创建一个强密码', type='password')

            st.markdown("###")
            sign_up_submit_button = st.form_submit_button(label='注册')

            if sign_up_submit_button:
                if valid_name_check is False:
                    st.error("请输入一个有效名字!")

                elif valid_email_check is False:
                    st.error("请输入有效邮箱!")

                elif unique_email_check is False:
                    st.error("邮箱号已被注册!")

                elif unique_username_check is False:
                    st.error(f'对不起, 昵称 {username_sign_up} 已经存在!')

                elif unique_username_check is None:
                    st.error('请输入一个非空昵称!')

                if valid_name_check is True and valid_email_check is True and unique_email_check is True \
                        and unique_username_check is True:
                    register_new_usr(name_sign_up, email_sign_up, username_sign_up, password_sign_up)
                    st.success("注册成功!")

    def forgot_password(self) -> None:
        """
        Creates the forgot password widget and after user authentication (email), triggers an email to the user
        containing a random password.
        """
        with st.form("忘记密码"):
            email_forgot_passwd = st.text_input("邮箱", placeholder='请输入您的邮箱')
            email_exists_check, username_forgot_passwd = check_email_exists(email_forgot_passwd)

            st.markdown("###")
            forgot_passwd_submit_button = st.form_submit_button(label='获取临时密码')

            if forgot_passwd_submit_button:
                if email_exists_check is False:
                    st.error("该邮箱从未注册过!")

                if email_exists_check is True:
                    random_password = generate_random_passwd()
                    send_passwd_in_email(username_forgot_passwd, email_forgot_passwd, random_password)
                    change_passwd(email_forgot_passwd, random_password)
                    st.success("临时密码发送成功!")

    def reset_password(self) -> None:
        """
        Creates the reset password widget and after user authentication (email and the password shared over that email),
        resets the password and updates the same in the _secret_auth_.json file.
        """
        with st.form("重置密码"):
            email_reset_passwd = st.text_input("邮箱", placeholder='请输入您的邮箱')
            email_exists_check, username_reset_passwd = check_email_exists(email_reset_passwd)

            current_passwd = st.text_input("当前密码",
                                           placeholder='请输入您在邮件中收到的当前密码')
            current_passwd_check = check_current_passwd(email_reset_passwd, current_passwd)

            new_passwd = st.text_input("新密码", placeholder='请输入新的强密码', type='password')

            new_passwd_1 = st.text_input("重新输入强密码", placeholder='请重新输入强密码', type='password')

            st.markdown("###")
            reset_passwd_submit_button = st.form_submit_button(label='重置密码')

            if reset_passwd_submit_button:
                if email_exists_check is False:
                    st.error("邮箱不存在!")

                elif current_passwd_check is False:
                    st.error("当前密码不正确!")

                elif new_passwd != new_passwd_1:
                    st.error("密码不匹配!")

                elif email_exists_check is True and current_passwd_check is True:
                    change_passwd(email_reset_passwd, new_passwd)
                    st.success("密码重置成功!")

    def logout_widget(self) -> None:
        """
        Creates the logout widget in the sidebar only if the user is logged in.
        """
        if st.session_state['LOGGED_IN'] is True:
            del_logout = st.sidebar.empty()
            del_logout.markdown("#")
            co1, co2 = del_logout.columns([1, 1])
            with co1:
                st.markdown(f"### 您好，{self.cookies['__login_signup_ui_username__']}")
            with co2:
                logout_click_check = st.button('🙋‍♂️退出登录')
            if logout_click_check is True:
                st.session_state['LOGOUT_BUTTON_HIT'] = True
                st.session_state['LOGGED_IN'] = False
                self.cookies['__login_signup_ui_username__'] = ''
                self.cookies.save()
                del_logout.empty()
                st.rerun()

    def nav_sidebar(self):
        """
        Creates the side navigaton bar
        """
        main_page_sidebar = st.sidebar.empty()
        with main_page_sidebar:
            selected_option = option_menu(
                menu_title='DMSearch',
                menu_icon='list-columns-reverse',
                icons=['box-arrow-in-right', 'person-plus', 'x-circle', 'arrow-counterclockwise'],
                options=['Login', 'Create Account', 'Forgot Password?', 'Reset Password'],
                styles={
                    "container": {"padding": "5px"},
                    "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px"}})
        return main_page_sidebar, selected_option

    def hide_menu(self) -> None:
        """
        Hides the streamlit menu situated in the top right.
        """
        st.markdown(""" <style>
        #MainMenu {visibility: hidden;}
        </style> """, unsafe_allow_html=True)

    def hide_footer(self) -> None:
        """
        Hides the 'made with streamlit' footer.
        """
        st.markdown(""" <style>
        footer {visibility: hidden;}
        </style> """, unsafe_allow_html=True)

    def build_login_ui(self):
        """
        Brings everything together, calls important functions.
        """
        if 'LOGGED_IN' not in st.session_state:
            st.session_state['LOGGED_IN'] = False

        if 'LOGOUT_BUTTON_HIT' not in st.session_state:
            st.session_state['LOGOUT_BUTTON_HIT'] = False

        auth_json_exists_bool = self.check_auth_json_file_exists('_secret_auth_.json')

        if auth_json_exists_bool is False:
            with open("_secret_auth_.json", "w") as auth_json:
                json.dump([], auth_json)

        main_page_sidebar, selected_option = self.nav_sidebar()

        if selected_option == 'Login':
            c1, c2, c3 = st.columns([3, 4, 3])
            with c2:
                self.login_widget()
            with c1:
                if st.session_state['LOGGED_IN'] is False:
                    self.animation('login/Bolsa de Trabajo.json')
            with c3:
                if st.session_state['LOGGED_IN'] is False:
                    self.animation('login/Animation - 1741661556218.json')

        if selected_option == 'Create Account':
            self.sign_up_widget()

        if selected_option == 'Forgot Password?':
            self.forgot_password()

        if selected_option == 'Reset Password':
            self.reset_password()

        self.logout_widget()

        if st.session_state['LOGGED_IN'] is True:
            main_page_sidebar.empty()

        if self.hide_menu_bool is True:
            self.hide_menu()

        if self.hide_footer_bool is True:
            self.hide_footer()

        if st.session_state['LOGGED_IN']:
            search_ui(self.cookies)


if __name__ == '__main__':
    __login__obj = LoginPage()
    __login__obj.build_login_ui()
