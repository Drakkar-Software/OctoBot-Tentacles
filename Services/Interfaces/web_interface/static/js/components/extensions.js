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

$(document).ready(function() {
    const showModalIfNecessary = () => {
        $(".modal").each((_, element) => {
            const jqueryelement = $(element);
            if (jqueryelement.data("show-by-default") == "True") {
                jqueryelement.modal();
            }
        })
    }

    const registerTriggerCheckout = () => {
        $("button[data-role=\"open-package-purchase\"]").click(() => {
            $("#select-payment-method-modal").modal();
        })
        $("button[data-role=\"open-checkout\"]").click(async (event) => {
            const button = $(event.currentTarget);
            const paymentMethod = button.data("payment-method")
            const url = button.data("checkout-api-url")
            const data = {
                paymentMethod: paymentMethod,
                redirectUrl: window.location.href
            }
            console.log("url", url, "data", data)
            const checkoutUrl = await async_send_and_interpret_bot_update(data, url, null)
            console.log("checkoutUrl", checkoutUrl)
            if(checkoutUrl.url === null){
                create_alert("success", "User already owns this extension", "");
            } else {
                window.open(checkoutUrl.url, '_blank').focus();
            }
        })
    }

    showModalIfNecessary();
    registerTriggerCheckout();
});