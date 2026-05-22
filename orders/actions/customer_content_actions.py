from orders.actions.base import BaseAction


class GetCustomerContentConfigAction(BaseAction):
    """Return customer-app UI content that can later be managed from admin."""

    def execute(self):
        return {
            'navigation': {
                'bottomNav': [
                    {'label': 'Home', 'icon': 'home', 'route': '/', 'exact': True},
                    {'label': 'Search', 'icon': 'search', 'route': '/search'},
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
            },
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
            },
            'referral': {
                'title': 'Refer and Earn',
                'subtitle': 'For every friend who places their first FlashDrop order.',
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
