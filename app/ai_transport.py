"""检查兼容 Chat Completions 的结束状态，不接收被截断的学习结论。"""


class CompletionTruncated(ValueError):
    pass


def completion_content(data):
    choice = data['choices'][0]
    reason = choice.get('finish_reason')
    if reason == 'length':
        raise CompletionTruncated('completion_token_limit')
    if reason not in (None, 'stop'):
        raise ValueError('completion_not_finished')
    return choice['message']['content']
