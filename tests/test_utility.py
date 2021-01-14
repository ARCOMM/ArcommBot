import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import unittest
from unittest import IsolatedAsyncioTestCase

from ArcommBot.cogs.utility import Utility
from mocking import *


class UtilityTest(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(self):
        self.cog = Utility("MockBot")
        self.logger = MockLogger()
        self.cog.logger = self.logger

        self.general_channel = MockChannel("general")
        channels = [self.general_channel]

        self.unreserved = MockColour(0)
        self.mockRoles = {
            "everyone"  : MockRole("everyone", self.unreserved),
            "Training"  : MockRole("Training", self.unreserved),
            "Pickup"    : MockRole("Pickup", self.unreserved),
            "Recruit"   : MockRole("Recruit", MockColour(1)),
            "Admin"     : MockRole("Admin", MockColour(2))
        }

        roles = [
            self.mockRoles["everyone"], self.mockRoles["Training"], self.mockRoles["Pickup"], 
            self.mockRoles["Recruit"], self.mockRoles["Admin"]
        ]
        
        self.guild = MockGuild("ARCOMM", channels, roles)
        self.user = MockUser(self.guild, "Sven_Axeman", [self.mockRoles["everyone"], self.mockRoles["Admin"], self.mockRoles["Pickup"]])   

    async def test_send_message(self):
        testString = "Test send_message"
        message = await self.cog.send_message(self.general_channel, testString)

        self.assertTrue(self.logger.findLog(LogSeverity.INFO, f"Sent message to {self.general_channel} : {testString}"))
        self.assertEqual(message.content, testString)

    async def test_reply(self):
        testString = "Test reply"
        originMessage = await self.general_channel.send("Origin message")
        message = await self.cog.reply(originMessage, testString)

        self.assertTrue(self.logger.findLog(LogSeverity.INFO, f"Sent message to {self.general_channel} : {testString}"))
        self.assertEqual(message.reference, originMessage)
        self.assertEqual(message.content, testString)

    async def test_getRoles(self):
        message = await self.user.mock_send(self.general_channel, "Test message")
        ctx = MockContext(message = message)

        roles = self.cog.getRoles(ctx)
        self.assertTrue(self.logger.findLog(LogSeverity.DEBUG, "getRoles called"))    
        self.assertEqual(roles, [self.mockRoles["Training"], self.mockRoles["Pickup"]])

        roles = self.cog.getRoles(ctx, sort = True)
        self.assertEqual(roles, [self.mockRoles["Pickup"], self.mockRoles["Training"]])
        
        roles = self.cog.getRoles(ctx, reserved = True)
        self.assertEqual(roles, [self.mockRoles["Training"], self.mockRoles["Pickup"], self.mockRoles["Recruit"], self.mockRoles["Admin"]])

        roles = self.cog.getRoles(ctx, reserved = True, sort = True)
        self.assertEqual(roles, [self.mockRoles["Admin"], self.mockRoles["Pickup"], self.mockRoles["Recruit"], self.mockRoles["Training"]])

        roles = self.cog.getRoles(ctx, personal = True)
        self.assertEqual(roles, [self.mockRoles["Pickup"]])

        roles = self.cog.getRoles(ctx, reserved = True, personal = True)
        self.assertEqual(roles, [self.mockRoles["Admin"], self.mockRoles["Pickup"]])

    async def test_searchRoles(self):
        message = await self.user.mock_send(self.general_channel, "Test message")
        ctx = MockContext(message = message)

        roles = self.cog.searchRoles(ctx, "pick")
        self.assertEqual(roles, None)

        roles = self.cog.searchRoles(ctx, "pickup")
        self.assertEqual(roles, self.mockRoles["Pickup"])

        roles = self.cog.searchRoles(ctx, "pick", autocomplete = True)
        self.assertEqual(roles, self.mockRoles["Pickup"])

        roles = self.cog.searchRoles(ctx, "admin")
        self.assertEqual(roles, None)

        roles = self.cog.searchRoles(ctx, "ad", autocomplete = True, reserved = True)
        self.assertEqual(roles, "RESERVED")

        roles = self.cog.searchRoles(ctx, "ad", autocomplete = True, reserved = True, censorReserved = False)
        self.assertEqual(roles, self.mockRoles["Admin"])

    # TODO: def test_timeUntil(self):

    # TODO: async def test_getResource(self):

    # TODO: async def test_setResource(self):

    async def test_on_command(self):
        message = await self.user.mock_send(self.general_channel, ".help opday")
        ctx = MockContext(None, message)

        await self.cog.on_command(ctx)
        self.assertTrue(self.logger.findLog(LogSeverity.INFO, f"[None] command [.help opday] called by [{self.user.name}]"))

        message = await self.user.mock_send(self.general_channel, ".opday")
        ctx = MockContext(MockCog("Public"), message)

        await self.cog.on_command(ctx)
        self.assertTrue(self.logger.findLog(LogSeverity.INFO, f"[Public] command [.opday] called by [{self.user.name}]"))

    # TODO: async def on_command_error(self):

if __name__ == '__main__':
    unittest.main()
