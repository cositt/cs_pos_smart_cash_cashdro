/** @odoo-module */

/**
 * Parche del Router de pos_self_order: sustituir el slot dinámico
 * <t t-slot="{{activeSlot}}" t-props="slotProps"/> por t-if/t-elif explícitos.
 * Evita el OwlError "this.child.mount is not a function" al navegar payment → confirmation.
 */
import { patch } from "@web/core/utils/patch";
import { xml, onWillRender } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { Router } from "@pos_self_order/app/router";
import { LandingPage } from "@pos_self_order/app/pages/landing_page/landing_page";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";
import { ProductPage } from "@pos_self_order/app/pages/product_page/product_page";
import { ComboPage } from "@pos_self_order/app/pages/combo_page/combo_page";
import { CartPage } from "@pos_self_order/app/pages/cart_page/cart_page";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";
import { EatingLocationPage } from "@pos_self_order/app/pages/eating_location_page/eating_location_page";
import { StandNumberPage } from "@pos_self_order/app/pages/stand_number_page/stand_number_page";
import { OrdersHistoryPage } from "@pos_self_order/app/pages/order_history_page/order_history_page";

const ROUTER_TEMPLATE = xml`
    <t t-if="this.activeSlot === 'default'">
        <LandingPage />
    </t>
    <t t-elif="this.activeSlot === 'product_list'">
        <ProductListPage />
    </t>
    <t t-elif="this.activeSlot === 'product'">
        <ProductPage productTemplate="this.selfOrder.models['product.template'].get(this.slotProps?.id)" />
    </t>
    <t t-elif="this.activeSlot === 'combo_selection'">
        <ComboPage productTemplate="this.selfOrder.models['product.template'].get(this.slotProps?.id)" />
    </t>
    <t t-elif="this.activeSlot === 'cart'">
        <CartPage/>
    </t>
    <t t-elif="this.activeSlot === 'payment'">
        <t t-component="this._routerComponents.PaymentPage" />
    </t>
    <t t-elif="this.activeSlot === 'confirmation'">
        <t
            t-component="this._routerComponents.ConfirmationPage"
            t-props="{ orderAccessToken: this.slotProps?.orderAccessToken, screenMode: this.slotProps?.screenMode }"
        />
    </t>
    <t t-elif="this.activeSlot === 'location'">
        <EatingLocationPage />
    </t>
    <t t-elif="this.activeSlot === 'stand_number'">
        <StandNumberPage />
    </t>
    <t t-elif="this.activeSlot === 'orderHistory'">
        <OrdersHistoryPage />
    </t>
    <t t-else="">
        <LandingPage />
    </t>
`;

patch(Router.prototype, {
    setup() {
        super.setup(...arguments);
        this.selfOrder = useSelfOrder();
        // Asegurar que el template resuelve componentes desde el scope del instance.
        this._routerComponents = Router.components;

        onWillRender(() => {
            try {
                const debug = "[CashDro][Router]";
                const activeSlot = this.activeSlot;
                const slotProps = this.slotProps;
                // Evitar spam: solo loguear en payment/confirmation.
                if (activeSlot === "payment" || activeSlot === "confirmation") {
                    const comps = Router.components || {};
                    console.log(debug, { activeSlot, slotProps });
                    console.log(`${debug}[components-info]`, {
                        keys: Object.keys(comps),
                        PaymentPageType: typeof comps.PaymentPage,
                        PaymentPageTemplate: comps.PaymentPage?.template,
                        ConfirmationPageType: typeof comps.ConfirmationPage,
                        ConfirmationPageTemplate: comps.ConfirmationPage?.template,
                    });
                }
            } catch (_) {
                // Solo debug.
            }
        });
    },
});

Router.components = {
    LandingPage,
    ProductListPage,
    ProductPage,
    ComboPage,
    CartPage,
    PaymentPage,
    ConfirmationPage,
    EatingLocationPage,
    StandNumberPage,
    OrdersHistoryPage,
};

Router.template = ROUTER_TEMPLATE;


