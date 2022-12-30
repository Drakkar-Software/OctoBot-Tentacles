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

    // for some reason this is not always working when leaving it to bootstrap
    const ensureModales = () => {
        $('button[data-toggle="modal"]').each((_, element) => {
            $(element).click((event) => {
                // TODO
                const element = $(event.target);
                element.parent().children(element.data("target")).modal();
                return
                const events = jQuery._data( event.target, "events" )
                log("events", events)
                if(events.click.length === 1){
                    const element = $(event.target);
                    element.parent().children(element.data("target")).modal();
                }
                // event.preventDefault();
            })
        })
    }

    const onReconnected = () => {
        const loader = $("#restart-loader");
        if(loader.length){
            // change current page when reconnected
            window.location.href = loader.data("redirect-url");
        }
    }

    ensureModales();
    registerReconnectedCallback(onReconnected);
});
