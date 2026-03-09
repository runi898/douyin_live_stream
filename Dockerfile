FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY douyin_live_stream.py .
COPY app.py .
COPY static/ static/

EXPOSE 5000

# 使用 gunicorn 生产级部署，增加超时时间防止等待页面时 worker timeout，开启访问日志向控制台输出
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
