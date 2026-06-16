from rest_framework import status
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = int(getattr(response, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR) or status.HTTP_500_INTERNAL_SERVER_ERROR)
    if code == status.HTTP_403_FORBIDDEN:
        code = status.HTTP_401_UNAUTHORIZED
        msg = "权限不足，无法访问"
    elif code == status.HTTP_404_NOT_FOUND:
        msg = "接口不存在"
    elif code == status.HTTP_400_BAD_REQUEST:
        msg = "参数格式错误"
    elif code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        msg = "系统繁忙，请稍后重试"
    else:
        msg = "请求失败"

    response.status_code = code
    response.data = {"code": code, "msg": msg, "message": msg, "data": {}}
    return response

