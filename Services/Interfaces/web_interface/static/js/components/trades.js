/*
 * Drakkar-Software OctoBot
 * Copyright (c) Drakkar-Software, All rights reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3.0 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.
 */

$(document).ready(function () {
    const handleClearButton = () => {
        $("#clear-trades-history-button").on("click", (event) => {
            if (confirm("Clear trades history ?") === false) {
                return false;
            }
            const url = $(event.currentTarget).data("url")
            const success = (updated_data, update_url, dom_root_element, msg, status) => {
                // reload page on success
                location.reload();
            }
            send_and_interpret_bot_update(null, url, null, success, generic_request_failure_callback)
        })
    }
    handleClearButton();
    $('#open_trades_datatable').DataTable({
        // order by date
        "order": [[7, "desc"]]
    })
});