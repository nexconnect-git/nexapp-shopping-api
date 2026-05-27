from orders.actions.base import BaseAction
from orders.data.customer_content_repo import CustomerContentBlockRepository


DEFAULT_HOME_ADS = [
    {
        'id': 'home-ad-grocery',
        'eyebrow': 'Today only',
        'title': 'Top picks for your kitchen',
        'subtitle': 'Curated products from live vendor catalogs.',
        'ctaLabel': 'Shop picks',
        'ctaUrl': '/search?q=grocery',
        'icon': 'shopping_basket',
        'tone': 'purple',
        'template': 'soft_card',
    },
    {
        'id': 'home-ad-offers',
        'eyebrow': 'Store promos',
        'title': 'Free delivery and fresh deals',
        'subtitle': 'Offers appear as vendors publish them.',
        'ctaLabel': 'See stores',
        'ctaUrl': '/stores',
        'icon': 'delivery_truck_speed',
        'tone': 'green',
        'template': 'soft_card',
    },
]

DEFAULT_HOME_ENGAGEMENT_BANNERS = [
    {
        'id': 'nextou-club',
        'eyebrow': 'Nextou Club',
        'title': 'Save more on repeat orders',
        'subtitle': 'Order again, collect offers, and keep your everyday essentials close.',
        'ctaLabel': 'Explore rewards',
        'ctaUrl': '/wallet',
        'icon': 'workspace_premium',
        'tone': 'green',
        'template': 'club_banner',
    },
]

DEFAULT_ADS = {
    'home': DEFAULT_HOME_ADS,
    'search': [
        {
            'id': 'search-ad',
            'eyebrow': 'Tip',
            'title': 'Use filters to find faster delivery',
            'subtitle': 'Sort by rating, delivery time, category, or price.',
            'ctaLabel': 'Open filters',
            'ctaUrl': '',
            'icon': 'tune',
            'tone': 'blue',
            'template': 'soft_card',
        },
    ],
    'storeListing': [
        {
            'id': 'store-listing-offers',
            'eyebrow': 'Running offers',
            'title': 'Shop vendor deals near you',
            'subtitle': 'Look for offer badges on store cards before checkout.',
            'ctaLabel': 'Browse stores',
            'ctaUrl': '/stores',
            'icon': 'local_offer',
            'tone': 'orange',
            'template': 'soft_card',
        },
    ],
    'storeDetail': [
        {
            'id': 'store-detail-offer',
            'eyebrow': 'Store offer',
            'title': 'Add more to unlock vendor deals',
            'subtitle': 'Final discounts and delivery estimates are confirmed at checkout.',
            'ctaLabel': 'Add products',
            'ctaUrl': '',
            'icon': 'sell',
            'tone': 'purple',
            'template': 'soft_card',
        },
    ],
}

DEFAULT_OFFERS_SHOP_BANNERS = [
    {
        'id': 'coupon-strip',
        'eyebrow': 'Collect deals',
        'title': 'Vendor offers update live',
        'subtitle': 'Coupon availability depends on your selected store, address, and cart value.',
        'ctaLabel': 'Browse stores',
        'ctaUrl': '/stores',
        'icon': 'redeem',
        'tone': 'purple',
        'template': 'soft_card',
    },
]

PLACEMENT_TO_CONFIG_KEY = {
    'home_ad': ('ads', 'home'),
    'home_engagement': ('home', 'engagementBanners'),
    'offers_shop': ('offers', 'shopBanners'),
    'search_ad': ('ads', 'search'),
    'store_listing_ad': ('ads', 'storeListing'),
    'store_detail_ad': ('ads', 'storeDetail'),
}


def _serialize_block(block):
    return {
        'id': str(block.id),
        'eyebrow': block.eyebrow,
        'title': block.title,
        'subtitle': block.subtitle,
        'ctaLabel': block.cta_label,
        'ctaUrl': block.cta_url,
        'icon': block.icon,
        'tone': block.tone,
        'template': block.template,
        'image': block.image,
    }


def _active_blocks_by_config_key():
    grouped = {}
    for block in CustomerContentBlockRepository().get_active():
        key = PLACEMENT_TO_CONFIG_KEY.get(block.placement)
        if not key:
            continue
        grouped.setdefault(key, []).append(_serialize_block(block))
    return grouped


class GetCustomerContentConfigAction(BaseAction):
    """Return customer-app UI content that can later be managed from admin."""

    def execute(self):
        dynamic_blocks = _active_blocks_by_config_key()
        ads = {
            name: dynamic_blocks.get(('ads', name), defaults)
            for name, defaults in DEFAULT_ADS.items()
        }
        engagement_banners = dynamic_blocks.get(
            ('home', 'engagementBanners'),
            DEFAULT_HOME_ENGAGEMENT_BANNERS,
        )
        offer_banners = dynamic_blocks.get(
            ('offers', 'shopBanners'),
            DEFAULT_OFFERS_SHOP_BANNERS,
        )

        return {
            'navigation': {
                'bottomNav': [
                    {'label': 'Home', 'icon': 'home', 'route': '/', 'exact': True},
                    {'label': 'Search', 'icon': 'search', 'route': '/search'},
                    {'label': 'Stores', 'icon': 'storefront', 'route': '/stores'},
                    {'label': 'Cart', 'icon': 'shopping_cart', 'route': '/cart', 'badge': 'cart'},
                    {'label': 'Orders', 'icon': 'receipt_long', 'route': '/orders'},
                    {'label': 'Account', 'icon': 'person', 'route': '/profile'},
                ],
                'footerGroups': [
                    {
                        'title': 'Shop',
                        'links': [
                            {'label': 'Stores', 'route': '/stores'},
                            {'label': 'Offers', 'route': '/offers'},
                            {'label': 'Search', 'route': '/search'},
                        ],
                    },
                    {
                        'title': 'Account',
                        'links': [
                            {'label': 'Orders', 'route': '/orders'},
                            {'label': 'Addresses', 'route': '/addresses'},
                            {'label': 'Wallet', 'route': '/wallet'},
                        ],
                    },
                    {
                        'title': 'Support',
                        'links': [
                            {'label': 'Help', 'route': '/help'},
                            {'label': 'My Issues', 'route': '/issues'},
                            {'label': 'Referral', 'route': '/referral'},
                        ],
                    },
                ],
            },
            'home': {
                'fallbackHero': {
                    'badge': 'Live now',
                    'title': 'Browse nearby stores',
                    'subtitle': 'Live catalog, prices, and availability update from the server.',
                    'ctaLabel': 'Shop now',
                    'ctaUrl': '/stores',
                    'image': 'assets/placeholders/store.svg',
                },
                'sectionTitles': {
                    'topStores': 'Top Stores',
                    'recommended': 'Recommended for you',
                },
                'categoryPromoCopy': 'Browse products from active stores',
                'loadingCatalogTitle': 'Loading catalog',
                'loadingCatalogSubtitle': 'Live store data will appear here',
                'banners': [],
                'engagementBanners': engagement_banners,
            },
            'ads': ads,
            'search': {
                'tabs': ['All', 'Stores', 'Products', 'Categories'],
                'subtitle': 'Showing results near your selected location',
                'emptyTitle': 'No matching results',
                'emptyFiltered': 'Your active filters may be hiding available items. Clear filters or try a different location.',
                'emptyDefault': 'Try another search term or change your delivery location.',
                'clearFiltersLabel': 'Clear filters',
            },
            'filters': {
                'title': 'Filters',
                'subtitle': 'Refine stores and products',
                'deliveryTitle': 'Delivery Speed',
                'sortTitle': 'Sort By',
                'offersTitle': 'Offers',
                'categoriesTitle': 'Categories',
                'priceTitle': 'Price Range',
                'resetLabel': 'Reset',
                'applyLabel': 'Apply Filters',
                'sortOptions': ['Relevance', 'Rating', 'Delivery Time', 'Price Low to High'],
                'quickFilters': [
                    {'label': 'Fast Delivery', 'icon': 'bolt', 'action': 'fast_delivery'},
                    {'label': 'Offers', 'icon': 'local_offer', 'action': 'offers'},
                    {'label': 'Ratings 4+', 'icon': 'star', 'action': 'rating_4_plus'},
                    {'label': 'Under budget', 'action': 'under_budget'},
                ],
            },
            'cart': {
                'miniCartTitle': 'Mini Cart',
                'emptyTitle': 'Your cart is empty',
                'emptyDescription': 'Browse nearby stores and add fresh essentials.',
                'emptyCta': 'Browse Stores',
                'browseCta': 'Browse products',
                'securePayment': 'Safe and secure payments',
            },
            'offers': {
                'title': 'Offers & Coupons',
                'subtitle': 'Live coupons from the active catalog',
                'emptyTitle': 'No active coupons right now',
                'emptyDescription': 'Available offers will appear here as soon as the catalog has active coupons.',
                'emptyCta': 'Browse stores',
                'shopBanners': offer_banners,
            },
            'referral': {
                'title': 'Refer and Earn',
                'subtitle': 'For every friend who places their first Nextou order.',
                'ctaLabel': 'Copy referral link',
                'codeTitle': 'Your Referral Code',
                'rewardsTitle': 'Your Rewards',
                'rewardsSubtitle': 'Total Earned',
                'unavailableCode': 'Referral code is not available',
                'copiedMessage': 'Referral code copied',
            },
            'help': {
                'title': 'Order Help',
                'subtitle': 'Tell us what went wrong with your order.',
                'formLabel': 'Need Help?',
                'messageLabel': 'Tell us more',
                'messagePlaceholder': 'Describe the issue, item name, and what went wrong...',
                'replyPlaceholder': 'Write your reply to support...',
                'submitLabel': 'Submit',
                'submittingLabel': 'Submitting...',
                'sendLabel': 'Send Message',
                'sendingLabel': 'Sending...',
                'ratingTitle': 'Rate your experience',
                'ratingPositive': 'Excellent',
                'ratingNegative': 'Needs improvement',
                'faqTitle': 'Common help topics',
                'fallbackTopics': ['Order delayed', 'Wrong or missing item', 'Payment issue', 'Refund status'],
            },
            'messages': {
                'locationPrompt': 'Set your delivery location to see available stores near you.',
                'loginPrompt': 'Sign in to continue with your order.',
            },
            'version': 1,
        }
