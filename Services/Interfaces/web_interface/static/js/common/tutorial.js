function getWebsiteLink(route, name) {
    return `<a class="" target="_blank" rel="noopener" href="${getWebsiteUrl()}${route}">${name}</a>`
}

function getDocsLink(route, name) {
    return `<a class="" target="_blank" rel="noopener" href="${getDocsUrl()}${route}">${name}</a>`
}

function getExchangesDocsLink(route, name) {
    return `<a class="" target="_blank" rel="noopener" href="${getExchangesDocsUrl()}${route}">${name}</a>`
}

_TUTORIALS = {
    home: () => {
        let profileName = "selected";
        if($(`span[data-selected-profile]`).length){
            profileName = $(`span[data-selected-profile]`).data("selected-profile");
        }
        return {
            steps: [
                {
                    title: 'Welcome to OctoBot',
                    intro: `Your OctoBot is now trading using the ${profileName} profile.`
                },
                {
                    title: 'Quickly navigate through your OctoBot',
                    element: document.querySelector('#main-nav-bar'),
                    intro: ''
                },
                {
                    title: 'Your live OctoBot',
                    element: document.querySelector('#main-nav-left-part'),
                    intro: 'See and configure your live OctoBot.'
                },
                {
                    title: 'Trading activity',
                    element: document.querySelector('#main-nav-trading'),
                    intro: `View your OctoBot's current open orders and trades history.`
                },
                {
                    title: 'Portfolio',
                    element: document.querySelector('#main-nav-portfolio'),
                    intro: `Quickly checkout your funds at any given time, on every exchange.`
                },
                {
                    title: 'Profile',
                    element: document.querySelector('#main-nav-profile'),
                    intro: `Change any setting about your profile (traded cryptocurrencies, exchanges, strategies, ...).`
                },
                {
                    title: 'Trading type',
                    element: document.querySelector('#main-nav-trading-type'),
                    intro: 'See if your Octobot is trading simulated or real funds.'
                },
                {
                    title: 'Test your profile',
                    element: document.querySelector('#main-nav-backtesting'),
                    intro: 'Backtest your current configuration using historical data.'
                },
                {
                    title: 'Community',
                    element: document.querySelector('#main-nav-community'),
                    intro: 'Access your OctoBot account and the OctoBot community stats.'
                },
                {
                    title: 'Customize your dashboard',
                    element: document.querySelector('#all-watched-markets'),
                    intro: 'Add watched markets from the Trading tab.'
                },
                {
                    title: "That's it !",
                    intro: 'We hope you will enjoy OctoBot. Use the <a class="blue-text" target="_blank"><i class="fa-solid fa-question"></i></a> buttons to learn more on how to use OctoBot'
                },
            ]
        }
    },

    profile: () => {
        return {
            steps: [
                {
                    title: 'Profile configuration',
                    intro: 'From this tab, you can configure your OctoBot profile.'
                },
                {
                    title: 'Select another profile',
                    element: document.querySelector('#profile-selector-link'),
                    intro: 'You can change the profile used by your OctoBot at any time.'
                },
                {
                    title: 'Customize your profiles',
                    element: document.querySelector('#edit-profiles-button'),
                    intro: 'You can create you own profiles based on existing ones.'
                },
                {
                    title: 'Set your profile strategy',
                    element: document.querySelector('#panelStrategies-tab'),
                    intro: "Select and configure your current profile's trading mode and configuration."
                },
                {
                    title: 'Select traded cryptocurrencies',
                    element: document.querySelector('#panelCurrency-tab'),
                    intro: "Select the cryptocurrencies to trade on your current profile."
                },
                {
                    title: 'Select exchanges',
                    element: document.querySelector('#panelExchanges-tab'),
                    intro: "Select the exchange(s) to trade on with your current profile."
                },
                {
                    title: 'Select trading configuration',
                    element: document.querySelector('#panelTrading-tab'),
                    intro: "Select whether to trade using simulated funds or your real funds on exchanges."
                },
                {
                    title: 'Save your changes',
                    element: document.querySelector('#save-config'),
                    intro: "When configuring your profile, changes saved when you hit 'save'."
                },
                {
                    title: 'See also',
                    intro: `More details on ${getWebsiteLink("/guides/#trading_modes", "the OctoBot guide")}.`
                },
            ]
        }
    },

    profile_selector: () => {
        return {
            steps: [
                {
                    title: 'Welcome to OctoBot',
                    intro: `To start with OctoBot, select the trading profile that you want to use at first.`
                },
                {
                    title: 'Choosing your profile',
                    element: document.querySelector('[data-target="#defaultModal"]'),
                    intro: `Find more details on each profile using the details button.`
                },
                {
                    title: 'Select your profile',
                    element: document.querySelector('.activate-profile-button'),
                    intro: `Once you found the right profile, just activate it.`
                },
                {
                    title: 'Get more profiles',
                    element: document.querySelector('.login_box'),
                    intro: `Use OctoBot cloud to add profiles to your OctoBot.`
                },
            ]
        }
    },

    automations: () => {
        return {
            steps: [
                {
                    title: 'Welcome to automations',
                    intro: `Here you can automate any action directly form your OctoBot.`
                },
                {
                    title: 'What are automations ?',
                    element: document.querySelector('#configEditor'),
                    intro: `Automations are actions your OctoBot can process on a given event or frequency.`
                },
                {
                    title: 'Example 1/2',
                    element: document.querySelector('#configEditor'),
                    intro: `Make your OctoBot send you a notification if your profitability increased by 10% in a day.`
                },
                {
                    title: 'Example 2/2',
                    element: document.querySelector('#configEditor'),
                    intro: `Cancel all open orders if the price of BTC/USDT crosses 70.000 USDT.`
                },
                {
                    title: 'Launch automations',
                    element: document.querySelector('#applyAutomations'),
                    intro: `Automations are started with your OctoBot and when hitting the "apply automations" button.`
                },
                {
                    title: 'Automations are saved in your profile',
                    element: document.querySelector('#page-title'),
                    intro: `You can quickly switch automations by switching profiles.`
                },
                {
                    title: 'Share automations',
                    element: document.querySelector('#page-title'),
                    intro: `As they are linked to a profile, you can share them with your profile.`
                },
            ]
        }
    },

    profitability: () => {
        return {
            steps: [
                {
                    title: 'Your profitability',
                    element: document.querySelector('#profitability-display'),
                    intro: 'Your OctoBot trading profitability compared to the market.'
                },
                {
                    title: 'See also',
                    intro: `More details on ${getDocsLink("/usage/understanding-profitability", "the OctoBot docs")}.`
                },
            ]
        }
    },

    account_exchanges: () => {
        return {
            steps: [
                {
                    title: 'Adding exchanges',
                    element: document.querySelector('#new-exchange-selector'),
                    intro: 'Add as many exchanges as you like. You can enable or disable them in each profile.'
                },
                {
                    title: 'Exchanges configuration',
                    intro: 'Exchange configurations are only required to trade with real funds on the exchange.'
                },
                {
                    title: 'See also',
                    intro: `More details on supported exchanges in the ${getExchangesDocsLink("", "OctoBot exchanges docs")}.`
                },
            ]
        }
    },

    backtesting: () => {
        return {
            steps: [
                {
                    title: 'Backtesting',
                    intro: 'Test your current profile using historical data.'
                },
                {
                    title: 'Get historical',
                    element: document.querySelector('#data-collector-link'),
                    intro: 'Download historical market data to test your profiles on.'
                },
                {
                    title: 'See also',
                    intro: `More details the ${getWebsiteLink("/guides/#backtesting", "backtesting guide")}.`
                },
            ]
        }
    },
}

function registerTutorial(tutorialName, callback){
    _TUTORIALS[tutorialName] = callback
}

function displayLocalTutorial(tutorialName){
    if(typeof _TUTORIALS[tutorialName] === "undefined"){
        console.error(`Tutorial not found ${tutorialName}`)
        return;
    }
    const defaultOptions = {
        disableInteraction: true,
        showProgress: true,
        showBullets: false,
    }
    introJs().setOptions(defaultOptions).setOptions(_TUTORIALS[tutorialName]()).start();
}

function startTutorialIfNecessary(tutorialName) {
    if($(`span[data-display-intro="True"]`).length === 0){
        return false;
    }
    displayLocalTutorial(tutorialName);
    return true;
}


$(document).ready(function () {
   $(`a[data-intro]`).each((_, element) => {
       $(element).on("click", (event) => {
           displayLocalTutorial($(event.currentTarget).data("intro"))
       })
   })
});
