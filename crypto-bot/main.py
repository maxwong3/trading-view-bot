import asyncio
import discord
from discord.ext import commands
from discord import Embed
import logging
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import sys
from fastapi import FastAPI, Request, HTTPException, status
from contextlib import asynccontextmanager
from shared import logger, queue
from db import pool
from bot import bot

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

load_dotenv()

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    task = asyncio.create_task(bot.start(os.getenv("DISCORD_TOKEN")))
    yield
    await bot.close()
    await task

app = FastAPI(lifespan=lifespan)


@app.get('/')
async def home():
    return {'Message': 'Running'}

@app.post('/webhook')
async def webhook(request: Request):
    try:
        json_data = await request.json()
        asyncio.run_coroutine_threadsafe(queue.put(json_data), bot.loop)
        # 200 Success
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
