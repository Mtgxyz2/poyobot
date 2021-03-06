from utils import Cog, is_admin, is_mod, NotAdminError, NotModError, group
from discord.ext import commands
import database
import importlib


class ModuleCog(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    @group(invoke_without_command=True)
    async def module(self, ctx):
        """Module command

Depending on your permissions, some of these commands might be unavailable."""
        await ctx.send("You need to specify a subcommand (load, unload, \
reload, list, activate, deactivate, info)")

    def get_module(self, name):
        return self.bot.extensions[f"mod.{name}"]

    def get_cog(self, name):
        return self.get_module(name).cog

    async def get_load_order(self, name):
        mod = importlib.import_module(f"mod.{name}")
        mods = []
        for modname in mod.dependencies:
            async for dep in self.get_load_order(modname):
                if dep not in mods:
                    yield dep
                    mods.append(dep)
        yield name

    async def get_unload_order(self, name):
        mod = self.get_cog(name)
        mods = []
        for modname in mod.dependents.copy():
            async for dep in self.get_unload_order(modname):
                if dep not in mods:
                    yield dep
                    mods.append(dep)
        yield name

    async def load_mod(self, name):
        async for mod in self.get_load_order(name):
            self.bot.load_extension(f"mod.{mod}")
            for dep in self.get_module(mod).dependencies:
                self.get_cog(dep).dependents.append(mod)

    async def unload_mod(self, name):
        async for mod in self.get_unload_order(name):
            await self.get_cog(mod).on_unload()
            for dep in self.get_module(mod).dependencies:
                dep_deps = self.get_cog(dep).dependents
                del dep_deps[dep_deps.index(mod)]
            self.bot.unload_extension(f"mod.{mod}")

    async def reload_mod(self, name):
        data = {}
        mods = []
        async for mod in self.get_unload_order(name):
            data[mod] = await self.get_cog(mod).on_reload_unload()
            await self.unload_mod(mod)
            mods.append(mod)
        for mod in reversed(mods):
            await self.load_mod(mod)
            await self.get_cog(mod).on_reload_load(data[mod])

    @module.command()
    @commands.is_owner()
    async def load(self, ctx, name: str):
        """Loads a module"""
        await self.load_mod(name)
        await ctx.send("👌")

    @module.command()
    @commands.is_owner()
    async def unload(self, ctx, name: str):
        """Unloads a module"""
        await self.unload_mod(name)
        await ctx.send("👌")

    @module.command()
    @commands.is_owner()
    async def reload(self, ctx, name: str):
        """Reloads a module"""
        await self.reload_mod(name)
        await ctx.send("👌")

    @module.command()
    async def list(self, ctx):
        """Lists loaded modules"""
        data = "```"
        async with ctx.typing():
            for modname, mod in self.bot.extensions.items():
                line = f"{modname} - enabled here: {mod.cog.check_once(ctx)}\n"
                if len(data) + len(line) + 3 >= 2000:
                    await ctx.send(data + "```")
                    data = "```"
                data += line
        if data != "```":
            await ctx.send(data + "```")

    async def set_overwrite(self, module, who, enabled):
        if who.id in module.no_overrides:
            del module.no_overrides[module.no_overrides.index(who.id)]
        if who.id in module.overrides:
            document = await database.db.enable.find_one(
                {"name": module._module.__name__,
                 "id": who.id})
        else:
            document = {"name": module._module.__name__, "id": who.id}

        document["enabled"] = enabled
        if who.id in module.overrides:
            await database.db.enable.replace_one({'_id': document['_id']},
                                                 document)
        else:
            await database.db.enable.insert_one(document)
        module.overrides[who.id] = enabled

    async def set_perm(self, ctx, name: str, global_: bool, user: bool,
                       server: bool, channel: bool, enable: bool):
        mod = self.bot.extensions[f"mod.{name}"]
        cog = mod.cog
        if global_ and not await self.bot.is_owner(ctx.message.author):
            raise commands.NotOwner("You need to be owner to do that")
        if server and not await is_admin(ctx.message.guild,
                                         ctx.message.author):
            raise NotAdminError("You need to have one of the following to do \
that: be owner, admin, manage guild, kick and ban members")
        if channel and not await is_mod(ctx.message.guild,
                                        ctx.message.author,
                                        ctx.message.channel):
            raise NotModError("You need to have one of the following to do \
that: be owner, admin, manage guild, kick and ban members, manage channels, \
manage messages")

        if global_:
            global_enable_tbl = database.db.global_enable
            global_enable = await global_enable_tbl.find_one(
                {
                    "name": cog._module.__name__
                }
            )
            global_enable["enabled"] = enable
            await global_enable_tbl.replace_one({"_id": global_enable["_id"]},
                                                global_enable)
            cog.global_enable = enable
            await cog.on_disable(None)
        if user:
            await self.set_overwrite(cog, ctx.message.author, enable)
            if not enable:
                await cog.on_disable(ctx.message.author)
        if server:
            await self.set_overwrite(cog, ctx.message.guild, enable)
            if not enable:
                await cog.on_disable(ctx.message.guild)
        if channel:
            await self.set_overwrite(cog, ctx.message.channel, enable)
            if not enable:
                await cog.on_disable(ctx.message.channel)

    @module.command()
    async def enable(self, ctx, name: str, type: str):
        """Enables a module"""
        types = {"global": (True, False, False, False),
                 "user": (False, True, False, False),
                 "server": (False, False, True, False),
                 "channel": (False, False, False, True)}
        await self.set_perm(ctx, name, *types[type], True)
        await ctx.send("👌")

    @module.command()
    async def disable(self, ctx, name: str, type: str):
        """Disables a module"""
        types = {"global": (True, False, False, False),
                 "user": (False, True, False, False),
                 "server": (False, False, True, False),
                 "channel": (False, False, False, True)}
        await self.set_perm(ctx, name, *types[type], False)
        await ctx.send("👌")

    @module.command()
    async def info(self, ctx, name: str):
        """Displays information about a loaded module"""
        mod = self.bot.extensions[f"mod.{name}"]

        outstr = f"""\
Module {mod.__name__} version {mod.__version__}

{mod.__doc__}

This module was written by {mod.__author__} and is released under \
{mod.__license__} on {mod.__website__}
        """
        await ctx.send(outstr)
