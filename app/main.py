from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import video, publish, account, interaction, search, creator, audit

app = FastAPI(
    title="短视频平台后端服务",
    description="为多个客户端提供内容与互动能力的短视频平台后端",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "短视频平台后端服务",
        "version": "1.0.0",
        "description": "为多个客户端提供内容与互动能力的短视频平台后端",
        "apis": {
            "video": "/api/video - 视频流接口",
            "publish": "/api/publish - 发布接口",
            "account": "/api/account - 账号接口",
            "interaction": "/api/interaction - 互动接口",
            "search": "/api/search - 搜索接口",
            "creator": "/api/creator - 创作者接口",
            "audit": "/api/audit - 审核接口",
        },
    }


app.include_router(video.router, prefix="/api/video", tags=["视频流接口"])
app.include_router(publish.router, prefix="/api/publish", tags=["发布接口"])
app.include_router(account.router, prefix="/api/account", tags=["账号接口"])
app.include_router(interaction.router, prefix="/api/interaction", tags=["互动接口"])
app.include_router(search.router, prefix="/api/search", tags=["搜索接口"])
app.include_router(creator.router, prefix="/api/creator", tags=["创作者接口"])
app.include_router(audit.router, prefix="/api/audit", tags=["审核接口"])


@app.on_event("startup")
async def startup_event():
    print("=" * 40)
    print("  短视频平台后端服务已启动")
    print("  服务地址: http://localhost:8000")
    print("  API文档: http://localhost:8000/docs")
    print("=" * 40)
    print()
    print("  API 分组：")
    print("  1. 视频流接口   - /api/video")
    print("  2. 发布接口     - /api/publish")
    print("  3. 账号接口     - /api/account")
    print("  4. 互动接口     - /api/interaction")
    print("  5. 搜索接口     - /api/search")
    print("  6. 创作者接口   - /api/creator")
    print("  7. 审核接口     - /api/audit")
    print()
    print("  测试账号 (x-user-id): u1 ~ u6")
    print("=" * 40)
