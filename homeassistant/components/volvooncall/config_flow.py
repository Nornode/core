"""Config flow for Volvo On Call integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from volvooncall import Connection

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import VolvoData
from .const import CONF_MUTABLE, CONF_SCANDINAVIAN_MILES, DOMAIN
from .errors import InvalidAuth

_LOGGER = logging.getLogger(__name__)


class VolvoOnCallConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """VolvoOnCall config flow."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step."""
        errors = {}
        defaults = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_REGION: None,
            CONF_MUTABLE: True,
            CONF_SCANDINAVIAN_MILES: False,
        }

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])

            if not self._reauth_entry:
                self._abort_if_unique_id_configured()

            try:
                await self.is_valid(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unhandled exception in user step")
                errors["base"] = "unknown"
            if not errors:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=self._reauth_entry.data | user_input
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        elif self._reauth_entry:
            for key in defaults:
                defaults[key] = self._reauth_entry.data.get(key)

        user_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD, default=defaults[CONF_PASSWORD]): str,
                vol.Required(CONF_REGION, default=defaults[CONF_REGION]): vol.In(
                    {"na": "North America", "cn": "China", None: "Rest of world"}
                ),
                vol.Optional(CONF_MUTABLE, default=defaults[CONF_MUTABLE]): bool,
                vol.Optional(
                    CONF_SCANDINAVIAN_MILES, default=defaults[CONF_SCANDINAVIAN_MILES]
                ): bool,
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=user_schema, errors=errors
        )

    async def async_step_import(self, import_data) -> FlowResult:
        """Import volvooncall config from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def is_valid(self, user_input):
        """Check for user input errors."""

        session = async_get_clientsession(self.hass)

        region: str | None = user_input.get(CONF_REGION)

        connection = Connection(
            session=session,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            service_url=None,
            region=region,
        )

        test_volvo_data = VolvoData(self.hass, connection, user_input)

        await test_volvo_data.auth_is_valid()
