#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author   : CJ

import re
import streamlit as st
from loguru import logger
# from alibabacloud_sample.nl2sql_retrieve import select_db
# from alibabacloud_sample.xiyan_nl2sql import select_db
from core.nl2sql_agent import select_db
import json
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from alibabacloud_sample.rag import rag_retrieve
from core.BI import preprocess_chart
from core.search_agent import CustomLLMThoughtLabeler, llm_invoke
from core.question_rewriting import rewrite
from core.search_agent import CustomStreamlitCallbackHandler
from core.recommend_drop_duplicates import get_cluster_df
from libs.dump import Save
import uuid
from core.BI import echarts_graph
from icon import title_icon, ai_icon, user_icon

# os.environ['LANGSMITH_TRACING'] = 'true'
# os.environ['LANGSMITH_ENDPOINT'] = 'https://api.smith.langchain.com'
# os.environ['LANGSMITH_API_KEY'] = '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'
# os.environ['LANGSMITH_PROJECT'] = 'dm-search'


st.markdown(
    """<style>
.stChatFloatingInputContainer {
            bottom: 0px; /* 调整输入框距离底部的距离 */
            width: 100% !important; /* 设置输入框宽度 */
            # height: 100px; /* 设置输入框高度 */
            # background-color: rgba(0, 0, 0, 0); /* 设置透明背景 */
        }
.chat-message {
    padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; display: flex
}
.chat-message.user {
    background-color: #042452;
}
.chat-message.bot {
    background-color: #1B3A64;
}
.chat-message .avatar {
    background-color: #1B3A64;
  width: 10%;
  height: 50%;
}
.chat-message .avatar img {
  max-width: 30px;
  max-height: 30px;
  border-radius: 50%;
  object-fit: cover;
}
.chat-message .message {
    background-color: #1B3A64;
  width: 100%;
  padding: 0 1.5rem;
  color: #fff;
}
.stDeployButton {
            visibility: hidden;
        }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.block-container {
    padding: 0rem 4rem 4rem 4rem;
}

.st-emotion-cache-16txtl3 {
    padding: 3rem 1.5rem;
}
.container {{
            background-color: #1B3A64;
            display: flex;
            align-items: flex-start;
        }}
.markdown-content {{
    flex: 1;
    margin-right: 20px;
}}
.copy-button {{
    padding: 10px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}}
.copy-button:hover {{
    background-color: #0056b3;
}}
.stDataFrame {
            background-color: #475063; /* 设置 DataFrame 的背景颜色 */
        }
.stLineChart {
    background-color: #475063; /* 设置 LineChart 的背景颜色 */
}
.stBarChart {
            background-color: #475063; /* 设置 LineChart 的背景颜色 */
        }
</style>
# """,
    unsafe_allow_html=True,
)

bot_template = """
<div class="chat-message bot">
    <div class="message">{{MSG}}</div>
</div>
"""

user_template = """
<div class="chat-message user">
    <div class="message">{{MSG}}</div>
</div>
"""


def print_ai_response(result_placeholder, response, select_result_text):
    """
    输出ai响应结果
    :param result_placeholder: 结果输出容器
    :param response: llm响应
    :param select_result_text: 查询结果
    :return:
    """
    response_content = ''
    reasoning_content = ''
    content = ''
    try:
        for message in response:
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs.get('reasoning_content'):
                reasoning_content += message.additional_kwargs.get('reasoning_content')
            if isinstance(message, dict) and message.get('output'):
                response_content += message['output'] + '\n'
            elif hasattr(message, 'content'):
                response_content += message.content
            else:
                response_content += ''
            try:
                if reasoning_content:
                    content = f"""\n\n###### 思考过程：\n\n```text\n{reasoning_content}\n```\n\n"""
                else:
                    content = ''
                response = f"""{content}{response_content}"""
                result_placeholder.markdown(bot_template.replace("{{MSG}}",
                                                                 response + select_result_text),
                                            unsafe_allow_html=True)
            except Exception as e:
                logger.warning(e)
    except Exception as e:
        logger.warning(e)
    response = f"""{content}{response_content}{select_result_text}"""
    return response


def style_reference(label):
    """渲染标签"""
    if label == '诉讼':
        text = f'<span style="background-color: #F56C6C;border-radius: 3px;">{label}</span>'
    elif label == '公告':
        text = f'<span style="background-color: #E6A23C;border-radius: 3px;">{label}</span>'
    elif label == '新闻':
        text = f'<span style="background-color: #67C23A;border-radius: 3px;">{label}</span>'
    else:
        text = f'<span style="background-color: #67C23A;border-radius: 3px;">{label}</span>'
    return text


def save_feedback(index):
    """持久化用户反馈"""
    save = Save()
    sql = f"""update dm_search_history set `feedback`='{st.session_state[f"feedback_{index}"]}' where `id`='{index}'"""
    logger.info(sql)
    save.cursor.execute(sql)
    save.connect.commit()
    save.close()


def handle_userinput_message(user_question):
    """处理用户输入消息"""
    st.chat_message('user', avatar=user_icon).write(
        user_template.replace("{{MSG}}", user_question),
        unsafe_allow_html=True,
    )
    ai = st.chat_message('assistant', avatar=ai_icon)
    placeholder = ai.empty()
    placeholder.write('知识库检索中...')
    chat_history = st.session_state.chat_history
    new_question = rewrite(chat_history, user_question)
    st.session_state.chat_history.append({'role': "user", 'content': user_question, 'new_question': new_question})
    logger.debug(f'origin: {user_question}, new_question: {new_question}')
    tp = ThreadPoolExecutor(2)
    param = {'news_knowledge': st.session_state.news_knowledge,
             'announcement_knowledge': st.session_state.announcement_knowledge,
             'lawsuit_knowledge': st.session_state.lawsuit_knowledge,
             'research_knowledge': st.session_state.research_knowledge
             }
    news_rag_thread = tp.submit(rag_retrieve, new_question, param)
    if st.session_state.comprehensive_flag:
        sql_thread = tp.submit(select_db, new_question)
    else:
        sql_thread = None
    if sql_thread is not None:
        db_select_result = sql_thread.result()
    else:
        db_select_result = {'context': '', 'data': pd.DataFrame(), 'select_sql_text': ''}
    news_rag_result, all_reference = news_rag_thread.result()
    placeholder.empty()
    if news_rag_result:
        news_rag_result = f"知识库检索结果：\n{news_rag_result}"
    if db_select_result['context']:
        db_select_result_content = f"数据库查询结果：\n{db_select_result['context']}"
    else:
        db_select_result_content = ''
    inputs = {"input": new_question, "chat_history": [],
              'select_context': f"""{db_select_result_content}\n\n{news_rag_result}"""}
    if not db_select_result['data'].empty:
        df = db_select_result['data']
        chart_type, x, y, df = preprocess_chart(df)
        db_select_result_content = f"数据库查询结果：\n{df.head(500).to_string(index=False)}"
        inputs['select_context'] = f"""{db_select_result_content}\n\n{news_rag_result}"""
        with ai.expander('**查询结果：**', expanded=True):
            st.dataframe(df)
        echarts_graph(x, y, df, chart_type, ai)
    agent_executor = st.session_state.conversation(st.session_state.model_name,
                                                   search_flag=st.session_state.search_flag)

    st_callback = CustomStreamlitCallbackHandler(
        parent_container=ai.container(),
        expand_new_thoughts=False,
        collapse_completed_thoughts=True,
        thought_labeler=CustomLLMThoughtLabeler())
    config = {"callbacks": [st_callback]}
    response = agent_executor.stream(input=inputs, config=config)
    result_placeholder = ai.empty()
    response_content = print_ai_response(result_placeholder, response, db_select_result['select_sql_text'])
    if st_callback.on_agent_finish(response):
        st_callback.thought_labeler.get_final_agent_thought_label()
    generate_sql = re.sub(".*?```sql\n(.*?)\n```.*?", r'\g<1>', db_select_result['select_sql_text'], flags=re.S)
    all_reference_text = json.dumps(all_reference, ensure_ascii=False)
    history_data = pd.DataFrame([{'username': st.session_state.username,
                                  'session_id': st.session_state.session_id,
                                  'origin_question': user_question,
                                  'rewrite_question': new_question,
                                  'generate_sql': generate_sql,
                                  'answer': response_content,
                                  'reference': all_reference_text
                                  }])
    save = Save()
    _, insert_id = save.insert(history_data, 'dm_search_history')
    save.close()
    ai.feedback(
        "thumbs",
        key=f"feedback_{insert_id}",
        on_change=save_feedback,
        args=[insert_id],
    )
    st.session_state.chat_history.append({'role': "assistant", 'content': response_content, 'reference': all_reference,
                                          'id': insert_id, 'feedback': st.session_state[f"feedback_{insert_id}"]})
    with ai.expander('参考资料：'):
        for item in all_reference:
            st.markdown(f"{style_reference(item[0])} [{item[1]}]({item[2]})", unsafe_allow_html=True)
    logger.info(f'response: {response_content}')
    ai.write('\n\n')
    ai.write('\n\n')
    ai.write('\n\n')
    tp.shutdown()


def show_history():
    """展示历史会话"""
    chat_history = st.session_state.chat_history
    for i, message in enumerate(chat_history):
        try:
            if message['role'] == 'user' and message['content']:
                st.chat_message(message['role'], avatar=user_icon).write(
                    user_template.replace("{{MSG}}", message['content']),
                    unsafe_allow_html=True,
                )
            elif message['content']:
                ai = st.chat_message(message['role'], avatar=ai_icon)
                ai.write(
                    bot_template.replace("{{MSG}}", message['content']), unsafe_allow_html=True
                )
                feedback = message["feedback"]
                _id = message['id']
                if f"feedback_{_id}" not in st.session_state:
                    st.session_state[f"feedback_{_id}"] = feedback
                ai.feedback(
                    "thumbs",
                    key=f"feedback_{_id}",
                    on_change=save_feedback,
                    args=[_id],
                )
                with ai.expander('参考资料：'):
                    all_reference = message.get('reference')
                    if all_reference is not None:
                        for item in message['reference']:
                            st.markdown(f"{style_reference(item[0])} [{item[1]}]({item[2]})", unsafe_allow_html=True)
        except Exception as e:
            logger.warning(e)


def load_history(session_id):
    """加载历史会话"""
    save = Save()
    session_conversation_sql = f"select origin_question, answer, reference, id, feedback from dm_search_history where session_id='{session_id}'"
    save.cursor.execute(session_conversation_sql)
    session_conversation_list = save.cursor.fetchall()
    save.close()
    conversation_history = []
    for r in session_conversation_list:
        if r[2]:
            reference = eval(r[2])
        else:
            reference = []
        r_json = [{'role': "user", 'content': r[0]},
                  {'role': "assistant", 'content': r[1], 'reference': reference, 'id': r[3], 'feedback': r[4]}]
        conversation_history.extend(r_json)
    st.session_state.chat_history = conversation_history
    st.session_state.session_id = session_id


def show_recommended():
    """展示推荐"""
    if st.session_state.chat_history:
        return
    save = Save()
    sql = 'select origin_question, count(*) as ctr from dm_search_history' \
          'group by origin_question ORDER BY ctr desc, create_time desc'
    save.cursor.execute(sql)
    result = save.cursor.fetchall()
    save.close()
    st.markdown('##### 大家都在搜：')
    col1, col2 = st.columns(2)
    df = pd.DataFrame(result, columns=['origin_question', 'ctr'])
    df = get_cluster_df(df)
    for i, item in df.iterrows():
        if i <= 10 and item['origin_question'] is not None and pd.notna(item['origin_question']):
            if i % 2 == 0:
                column = col1
            else:
                column = col2
            column.button(item['origin_question'], key=f'ctr_{i}',
                          on_click=handle_userinput_message, args=(item['origin_question'],))


def clear_history():
    """清空历史记录"""
    st.session_state.chat_history = []
    st.session_state.session_id = uuid.uuid4()


def search_ui(cookies):
    """UI主界面"""
    st.header("DM Search")
    # 初始化会话状态
    if 'empty_container' not in st.session_state:
        st.session_state.empty_container = st.empty()
    if "conversation" not in st.session_state:
        st.session_state.conversation = llm_invoke
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4()
    if 'cookies' not in st.session_state:
        st.session_state.cookies = cookies
    username = cookies.get('__login_signup_ui_username__', '')
    if 'username' not in st.session_state or username:
        st.session_state.username = username

    with st.sidebar:
        st.image(title_icon, width=200)
        st.session_state.model_name = st.selectbox(
            "模型：",
            ('qwq-plus', 'qwen-max', 'qwen-plus', 'qwen-turbo', 'deepseek-v3', 'deepseek-r1',
             'deepseek-r1-distill-qwen-1.5b', 'deepseek-r1-distill-llama-8b',
             'deepseek-r1-distill-llama-70b'))
        st.session_state.search_flag = st.toggle('开启联网')
        st.button("开启新对话", on_click=clear_history, use_container_width=True)
        st.subheader('选择板块问答', divider='rainbow')
        col1, col2 = st.columns(2)
        st.session_state.comprehensive_flag = col1.toggle('NL2SQL问答')
        st.session_state.sentiment_flag = col2.toggle('舆情问答', value=True)
        st.subheader('选择知识库', divider='rainbow')
        col3, col4 = st.columns(2)
        st.session_state.news_knowledge = col3.toggle('舆情知识库', value=True)
        st.session_state.announcement_knowledge = col4.toggle('公告知识库')
        st.session_state.lawsuit_knowledge = col3.toggle('诉讼知识库')
        st.session_state.research_knowledge = col4.toggle('研报知识库')
        save = Save()
        sql = f'select distinct session_id, origin_question from dm_search_history ' \
              f'where username = "{st.session_state.username}" ' \
              f'group by session_id order by create_time desc'
        save.cursor.execute(sql)
        history_list = save.cursor.fetchall()
        save.close()
        st.subheader('会话管理', divider='rainbow')
        with st.expander('历史对话'):
            for record in history_list:
                if record:
                    st.button(record[1][:60], key=record[0], on_click=load_history, args=(record[0],),
                              use_container_width=True)

    user_question = st.chat_input("问一问~ (尝试输入sql试试)")
    with st.container(border=True):
        show_history()
        if user_question:
            logger.info(f'user_question: {user_question}')
            # if st.session_state.conversation is not None:
            handle_userinput_message(user_question)
        else:
            show_recommended()
