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


$(document).ready(async () => {
    const registerScaleSelector = () => {
        $('a[data-action="change-scale"]').on("click", (event) => {
            const selector = $(event.currentTarget);
            if(!selector.hasClass("active")){
                selector.addClass("active");
                $('a[data-action="change-scale"]').each((_, jselement) => {
                    const element = $(jselement);
                    if(element.data("scale") !== selector.data("scale")){
                        element.removeClass("active");
                    }
                })
                updatePnl(true);
            }
        })
    }
    const getScale = () => {
        return $('a.nav-link.scale-selector.active').data("scale");
    }
    const hideLoader = () => {
        $("#pnl-waiter").hide();
    }
    const updatePnl = async (update) => {
        const pnlHistory = await fetchPnlHistory(getScale());
        loadPnlFullChartHistory(pnlHistory, update);
        loadPnlTableHistory(pnlHistory, update);
        hideLoader();
    }
    await updatePnl(false);
    registerScaleSelector();
});
