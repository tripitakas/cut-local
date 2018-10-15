# cut-local

基于 tornado 的切栏校对应用（本地版，无云服务存储和任务管理）。

## 安装

1. 安装 Python 3.6 和 pip。

2. 安装本项目的 Python 依赖包：
```
pip install -r requirements.txt
```

3. 将栏切分的 img 和 pos 文件夹复制到 static 目录下，有增加或改动后直接更新即可。

## 运行

- 在 PyCharm 中选中 app.py 右键点“Debug app”，或在命令行中运行 `python app.py`。

- 在浏览器中打开 [localhost:8001](http://localhost:8001)
