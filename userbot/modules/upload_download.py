# Copyright (C) 2019 The Raphielscape Company LLC.
#
# Licensed under the Raphielscape Public License, Version 1.c (the "License");
# you may not use this file except in compliance with the License.
#
# The entire source code is OSSRPL except
# 'download, uploadir, uploadas, upload' which is MPL
# License: MPL and OSSRPL
""" Userbot module which contains everything related to
     downloading/uploading from/to the server. """

import asyncio
import math
import os
import time
from datetime import datetime
from urllib.parse import unquote_plus

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from natsort import os_sorted
from pySmartDL import SmartDL
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

from userbot import CMD_HELP, LOGS, TEMP_DOWNLOAD_DIRECTORY
from userbot.events import register
from userbot.utils import humanbytes, progress
from userbot.utils.FastTelethon import download_file, upload_file


async def run_cmd(cmd: List) -> (bytes, bytes):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await process.communicate()
    t_resp = out.strip()
    e_resp = err.strip()
    return t_resp, e_resp


@register(pattern=r"^\.dl(?: |$)(.*)", outgoing=True)
async def download(target_file):
    """For .download command, download files to the userbot's server."""
    await target_file.edit("`Processing...`")
    input_str = target_file.pattern_match.group(1)
    replied = await target_file.get_reply_message()
    if not os.path.isdir(TEMP_DOWNLOAD_DIRECTORY):
        os.makedirs(TEMP_DOWNLOAD_DIRECTORY)
    if input_str:
        url = input_str
        file_name = unquote_plus(os.path.basename(url))
        if "|" in input_str:
            url, file_name = input_str.split("|")
            url = url.strip()
            # https://stackoverflow.com/a/761825/4723940
            file_name = file_name.strip()
            head, tail = os.path.split(file_name)
            if head:
                if not os.path.isdir(
                    os.path.join(
                        TEMP_DOWNLOAD_DIRECTORY,
                        head)):
                    os.makedirs(os.path.join(TEMP_DOWNLOAD_DIRECTORY, head))
                    file_name = os.path.join(head, tail)
        downloaded_file_name = TEMP_DOWNLOAD_DIRECTORY + "" + file_name
        downloader = SmartDL(url, downloaded_file_name, progress_bar=False)
        downloader.start(blocking=False)
        c_time = time.time()
        display_message = None
        while not downloader.isFinished():
            status = downloader.get_status().capitalize()
            total_length = downloader.filesize if downloader.filesize else None
            downloaded = downloader.get_dl_size()
            now = time.time()
            diff = now - c_time
            percentage = downloader.get_progress() * 100
            speed = downloader.get_speed()
            progress_str = "[{0}{1}] `{2}%`".format(
                "".join(["●" for i in range(math.floor(percentage / 10))]),
                "".join(["○" for i in range(10 - math.floor(percentage / 10))]),
                round(percentage, 2),
            )
            estimated_total_time = downloader.get_eta(human=True)
            try:
                current_message = (
                    f"`Name` : `{file_name}`\n"
                    "Status"
                    f"\n**{status}**... | {progress_str}"
                    f"\n{humanbytes(downloaded)} of {humanbytes(total_length)}"
                    f" @ {humanbytes(speed)}"
                    f"\n`ETA` -> {estimated_total_time}"
                )

                if round(
                        diff %
                        15.00) == 0 and current_message != display_message:
                    await target_file.edit(current_message)
                    display_message = current_message
            except Exception as e:
                LOGS.info(str(e))
        if downloader.isSuccessful():
            await target_file.edit(
                "Downloaded to `{}` successfully !!".format(downloaded_file_name)
            )
        else:
            await target_file.edit("Incorrect URL\n{}".format(url))
    elif replied:
        if not replied.media:
            return await target_file.edit("`Reply to file or media `")
        try:
            media = replied.media
            if hasattr(media, "document"):
                file = media.document
                mime_type = file.mime_type
                filename = replied.file.name
                if not filename:
                    if "audio" in mime_type:
                        filename = (
                            "audio_" +
                            datetime.now().isoformat(
                                "_",
                                "seconds") +
                            ".ogg")
                    elif "video" in mime_type:
                        filename = (
                            "video_" +
                            datetime.now().isoformat(
                                "_",
                                "seconds") +
                            ".mp4")
                outdir = TEMP_DOWNLOAD_DIRECTORY + filename
                c_time = time.time()
                start_time = datetime.now()
                with open(outdir, "wb") as f:
                    result = await download_file(
                        client=target_file.client,
                        location=file,
                        out=f,
                        progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                            progress(d, t, target_file, c_time, "[DOWNLOAD]", input_str)
                        ),
                    )
            else:
                start_time = datetime.now()
                result = await target_file.client.download_media(
                    media, TEMP_DOWNLOAD_DIRECTORY
                )
            dl_time = (datetime.now() - start_time).seconds
        except Exception as e:  # pylint:disable=C0103,W0703
            await target_file.edit(str(e))
        else:
            try:
                await target_file.edit(
                    "Downloaded to `{}` in `{}` seconds.".format(result.name, dl_time)
                )
            except AttributeError:
                await target_file.edit(
                    "Downloaded to `{}` in `{}` seconds.".format(result, dl_time)
                )
    else:
        await target_file.edit("See `.help download` for more info.")


async def get_video_thumb(file, output):
    """Get video thumbnail"""
    command = [
        "ffmpeg",
        "-i",
        file,
        "-ss",
        "00:00:01.000",
        "-vframes",
        "1",
        output]
    t_resp, e_resp = await run_cmd(command)
    if os.path.lexists(output):
        return output
    else:
        LOGS.info(t_resp)
        LOGS.info(e_resp)
        return None


@register(pattern=r"^\.up (.*)", outgoing=True)
async def upload(event):
    if event.fwd_from:
        return
    await event.edit("`Processing...`")
    input_str = event.pattern_match.group(1)
    if os.path.exists(input_str):
        if os.path.isfile(input_str):
            c_time = time.time()
            start_time = datetime.now()
            file_name = os.path.basename(input_str)
            thumb = None
            attributes = []
            with open(input_str, "rb") as f:
                result = await upload_file(
                    client=event.client,
                    file=f,
                    name=file_name,
                    progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                        progress(d, t, event, c_time, "[FILE - UPLOAD]", input_str)
                    ),
                )
            up_time = (datetime.now() - start_time).seconds
            if input_str.lower().endswith(("mp4", "mkv", "webm")):
                thumb = await get_video_thumb(input_str, "thumb_image.jpg")
                metadata = extractMetadata(createParser(input_str))
                duration = 0
                width = 0
                height = 0
                if metadata.has("duration"):
                    duration = metadata.get("duration").seconds
                if metadata.has("width"):
                    width = metadata.get("width")
                if metadata.has("height"):
                    height = metadata.get("height")
                attributes = [
                    DocumentAttributeVideo(
                        duration=duration,
                        w=width,
                        h=height,
                        round_message=False,
                        supports_streaming=True,
                    )
                ]
            elif input_str.lower().endswith(("mp3", "flac", "wav")):
                metadata = extractMetadata(createParser(input_str))
                duration = 0
                artist = ""
                title = ""
                if metadata.has("duration"):
                    duration = metadata.get("duration").seconds
                if metadata.has("title"):
                    title = metadata.get("title")
                if metadata.has("artist"):
                    artist = metadata.get("artist")
                attributes = [
                    DocumentAttributeAudio(
                        duration=duration,
                        title=title,
                        performer=artist,
                    )
                ]
            await event.client.send_file(
                event.chat_id,
                result,
                thumb=thumb,
                caption=file_name,
                force_document=False,
                allow_cache=False,
                reply_to=event.message.id,
                attributes=attributes,
            )
            if thumb is not None:
                os.remove(thumb)
            await event.edit(f"Uploaded successfully in `{up_time}` seconds.")
        elif os.path.isdir(input_str):
            start_time = datetime.now()
            lst_files = []
            for root, dirs, files in os.walk(input_str):
                for file in files:
                    lst_files.append(os.path.join(root, file))
            if len(lst_files) == 0:
                return await event.edit(f"`{input_str}` is empty.")
            await event.edit(f"Found `{len(lst_files)}` files. Now uploading...")
            for files in os_sorted(lst_files):
                file_name = os.path.basename(files)
                thumb = None
                attributes = []
                msg = await event.reply(f"Uploading `{files}`")
                with open(files, "rb") as f:
                    result = await upload_file(
                        client=event.client,
                        file=f,
                        name=file_name,
                    )
                if file_name.lower().endswith(("mp4", "mkv", "webm")):
                    thumb = await get_video_thumb(files, "thumb_image.jpg")
                    metadata = extractMetadata(createParser(files))
                    duration = 0
                    width = 0
                    height = 0
                    if metadata.has("duration"):
                        duration = metadata.get("duration").seconds
                    if metadata.has("width"):
                        width = metadata.get("width")
                    if metadata.has("height"):
                        height = metadata.get("height")
                    attributes = [
                        DocumentAttributeVideo(
                            duration=duration,
                            w=width,
                            h=height,
                            round_message=False,
                            supports_streaming=True,
                        )
                    ]
                elif file_name.lower().endswith(("mp3", "flac", "wav")):
                    metadata = extractMetadata(createParser(files))
                    duration = 0
                    title = ""
                    artist = ""
                    if metadata.has("duration"):
                        duration = metadata.get("duration").seconds
                    if metadata.has("title"):
                        title = metadata.get("title")
                    if metadata.has("artist"):
                        artist = metadata.get("artist")
                    attributes = [
                        DocumentAttributeAudio(
                            duration=duration,
                            title=title,
                            performer=artist,
                        )
                    ]
                await event.client.send_file(
                    event.chat_id,
                    result,
                    thumb=thumb,
                    caption=file_name,
                    force_document=False,
                    allow_cache=False,
                    attributes=attributes,
                )
                await msg.delete()
                if thumb is not None:
                    os.remove(thumb)

            await event.delete()
            up_time = (datetime.now() - start_time).seconds
            await event.respond(
                f"Uploaded `{len(lst_files)}` files in `{input_str}` folder "
                f"in `{up_time}` seconds."
            )
    else:
        await event.edit("`404: File/Folder Not Found`")


CMD_HELP.update(
    {
        "download": "✘ Pʟᴜɢɪɴ : Downloads"
        "\n\n⚡𝘾𝙈𝘿⚡: `.dl` <Link> | <Filename> (Optional)"
        "\n↳ : Downloads File From URL to The Server."
        "\n\n⚡𝘾𝙈𝘿⚡: `.dl` <Reply to File>"
        "\n↳ : Downloads File From the Replied File/Media."
        "\n\n⚡𝘾𝙈𝘿⚡: `.up` <File/Folder Path in Server>"
        "\n↳ : Uploads a Locally Stored File/Folder to The Chat."
    }
)
