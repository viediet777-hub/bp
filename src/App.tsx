import React, { useState, useEffect } from 'react';
import {
  ShoppingBag,
  Search,
  ShoppingCart,
  User as UserIcon,
  Sparkles,
  MapPin,
  Trash2,
  Plus,
  ArrowRight,
  Copy,
  ExternalLink,
  CheckCircle2,
  X,
  Navigation,
  KeyRound,
  FileCode2,
  CreditCard,
  QrCode
} from 'lucide-react';
import { Product, CartItem, Address, Order, FODOffer } from './types';
import { INITIAL_PRODUCTS } from './data/mockProducts';

export default function App() {
  const [tab, setTab] = useState<'home' | 'search' | 'cart' | 'account'>('home');
  const [userId] = useState(() => {
    try {
      const tg = (window as unknown as { Telegram?: { WebApp?: { initDataUnsafe?: { user?: { id?: number } } } } }).Telegram?.WebApp;
      if (tg?.initDataUnsafe?.user?.id) return String(tg.initDataUnsafe.user.id);
      let local = localStorage.getItem('fod_uid');
      if (!local) {
        local = '9' + Math.random().toString().slice(2, 8);
        localStorage.setItem('fod_uid', local);
      }
      return local;
    } catch {
      return '948201';
    }
  });

  // State
  const [offer, setOffer] = useState<FODOffer>({
    title: 'Upto',
    text: '₹200 OFF',
    subtitle: 'on 1st order',
    bucket: 200,
    display_bucket: 200,
    display_text: 'Upto ₹200 OFF',
    duration: 3,
    live: true
  });
  const [isRolling, setIsRolling] = useState(false);
  const [toastMsg, setToastMsg] = useState<{ text: string; kind?: 'ok' | 'err' } | null>(null);

  // Search and products
  const [searchQuery, setSearchQuery] = useState('');
  const [products] = useState<Product[]>(INITIAL_PRODUCTS);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>(INITIAL_PRODUCTS);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedSizeId, setSelectedSizeId] = useState<number>(0);

  // Cart
  const [cart, setCart] = useState<CartItem[]>([
    {
      id: 'cart-1',
      product_id: 101,
      name: 'Anarkali Floral Embroidered Rayon Kurti Set with Dupatta',
      price: 249,
      mrp: 799,
      image: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=500&auto=format&fit=crop&q=80',
      qty: 1,
      variation_name: 'M'
    }
  ]);
  const [tombstones, setTombstones] = useState<Set<number>>(new Set());

  // Addresses
  const [addresses, setAddresses] = useState<Address[]>([
    {
      id: 1,
      name: 'Vijay Singh',
      mobile: '9876543210',
      pin: '302001',
      city: 'Jaipur',
      state: 'Rajasthan',
      address_line_1: 'Plot 42, Civil Lines, Near Metro Pillar 12',
      is_default: true
    }
  ]);
  const [showAddressSheet, setShowAddressSheet] = useState(false);
  const [newAddress, setNewAddress] = useState({
    name: '',
    mobile: '',
    pin: '',
    city: '',
    state: '',
    address_line_1: ''
  });
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);

  // Checkout & Payment
  const [showCheckoutSheet, setShowCheckoutSheet] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'COD' | 'UPI'>('COD');
  const [showQrModal, setShowQrModal] = useState(false);
  const [currentUpiUri, setCurrentUpiUri] = useState('');
  const [pendingOrderNum, setPendingOrderNum] = useState('');
  const [lastPlacedOrder, setLastPlacedOrder] = useState<Order | null>(null);

  // Account
  const [isLinked, setIsLinked] = useState(true);
  const [linkedPhone, setLinkedPhone] = useState('9876543210');
  const [linkedUid, setLinkedUid] = useState('7428192');
  const [otpPhone, setOtpPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [jsonInput, setJsonInput] = useState('');

  // Orders
  const [orders, setOrders] = useState<Order[]>([
    {
      order_num: '84920192',
      meesho_order_num: 'MSH-84920192',
      items_text: 'Oversized Cotton Drop-Shoulder Graphic Print T-Shirt x1',
      total: 189,
      status: 'confirmed',
      payment_method: 'UPI',
      created_at: Date.now() - 86400000 * 2,
      address: 'Plot 42, Civil Lines, Jaipur'
    }
  ]);

  // Trigger Toast helper
  const showToast = (text: string, kind?: 'ok' | 'err') => {
    setToastMsg({ text, kind });
    setTimeout(() => setToastMsg(null), 2500);
  };

  // Offer Rolling Logic (180 - 220 bucket pool)
  const handleRollFOD = () => {
    setIsRolling(true);
    setTimeout(() => {
      const buckets = [220, 210, 200, 190, 180];
      const rolled = buckets[Math.floor(Math.random() * buckets.length)];
      setOffer({
        title: 'Upto',
        text: `₹${rolled} OFF`,
        subtitle: 'on 1st order',
        bucket: rolled,
        display_bucket: rolled,
        display_text: `Upto ₹${rolled} OFF`,
        duration: 3,
        live: true
      });
      setIsRolling(false);
      showToast(`Locked Best Offer: ₹${rolled} OFF!`, 'ok');
    }, 600);
  };

  // Search filtering
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredProducts(products);
    } else {
      const q = searchQuery.toLowerCase();
      setFilteredProducts(
        products.filter(
          p => p.name.toLowerCase().includes(q) || (p.discount_text && p.discount_text.toLowerCase().includes(q))
        )
      );
    }
  }, [searchQuery, products]);

  // Cart operations (Strictly + and Delete only, NO decrease button)
  const handleAddToCart = (product: Product, buyNow = false) => {
    const size = product.sizes?.find(s => s.id === selectedSizeId)?.name || 'Free Size';
    setCart(prev => {
      const existing = prev.find(item => item.product_id === product.product_id);
      if (existing) {
        return prev.map(item =>
          item.product_id === product.product_id ? { ...item, qty: item.qty + 1 } : item
        );
      }
      return [
        ...prev,
        {
          id: `cart-${Date.now()}`,
          product_id: product.product_id,
          name: product.name,
          price: product.price,
          mrp: product.mrp,
          image: product.image,
          qty: 1,
          variation_name: size
        }
      ];
    });

    // Remove from tombstone set if re-added deliberately
    setTombstones(prev => {
      const copy = new Set(prev);
      copy.delete(product.product_id);
      return copy;
    });

    setSelectedProduct(null);
    showToast('Added to Cart ✓', 'ok');
    if (buyNow) {
      setTab('cart');
    }
  };

  const handleIncreaseQty = (index: number) => {
    setCart(prev =>
      prev.map((item, i) => (i === index ? { ...item, qty: item.qty + 1 } : item))
    );
  };

  const handleDeleteItem = (index: number) => {
    const item = cart[index];
    if (!item) return;

    // Add to tombstone (300s TTL rule)
    setTombstones(prev => new Set(prev).add(item.product_id));

    // Remove locally
    setCart(prev => prev.filter((_, i) => i !== index));
    showToast('Item removed (Tombstoned for 300s) ✓', 'ok');

    // Simulate 4s delayed remote pull
    setTimeout(() => {
      console.log(`[Tombstone Sync] Background reconcile completed for pid: ${item.product_id}`);
    }, 4000);
  };

  // Delivery Address Calculations
  const defaultAddress = addresses.find(a => a.is_default) || addresses[0];

  // Price calculations
  const productPrice = cart.reduce((acc, item) => acc + item.mrp * item.qty, 0);
  const cartSubtotal = cart.reduce((acc, item) => acc + item.price * item.qty, 0);
  const totalDiscounts = Math.max(0, productPrice - cartSubtotal);
  const codAmount = cartSubtotal;
  const upiPrepaidDiscount = codAmount >= 60 ? 28 : (codAmount >= 20 ? 14 : 5);
  const upiAmount = Math.max(1, codAmount - upiPrepaidDiscount);
  const effectiveTotal = paymentMethod === 'COD' ? codAmount : upiAmount;

  // Browser Geolocation Detection
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      showToast('Geolocation is not supported by your browser', 'err');
      return;
    }
    setIsDetectingLocation(true);
    navigator.geolocation.getCurrentPosition(
      pos => {
        setIsDetectingLocation(false);
        const { latitude, longitude } = pos.coords;
        // Stub Indian geocode resolution
        setNewAddress(prev => ({
          ...prev,
          city: 'Jaipur',
          state: 'Rajasthan',
          pin: '302001',
          address_line_1: prev.address_line_1 || `Location lat: ${latitude.toFixed(3)}, lng: ${longitude.toFixed(3)}`
        }));
        showToast('Detected: Jaipur, Rajasthan (302001)', 'ok');
      },
      () => {
        setIsDetectingLocation(false);
        // Fallback default
        setNewAddress(prev => ({
          ...prev,
          city: 'New Delhi',
          state: 'Delhi',
          pin: '110001'
        }));
        showToast('Location permission denied; default set to Delhi', 'ok');
      },
      { timeout: 8000 }
    );
  };

  const handleSaveAddress = () => {
    if (!newAddress.name || !newAddress.mobile || !newAddress.pin || !newAddress.address_line_1) {
      showToast('Please fill all required address fields', 'err');
      return;
    }
    const created: Address = {
      id: Date.now(),
      name: newAddress.name,
      mobile: newAddress.mobile,
      pin: newAddress.pin,
      city: newAddress.city || 'Jaipur',
      state: newAddress.state || 'Rajasthan',
      address_line_1: newAddress.address_line_1,
      is_default: true
    };
    setAddresses(prev => [created, ...prev.map(a => ({ ...a, is_default: false }))]);
    setShowAddressSheet(false);
    setNewAddress({ name: '', mobile: '', pin: '', city: '', state: '', address_line_1: '' });
    showToast('New Address Saved & Selected ✓', 'ok');
  };

  // Place Order Flow
  const handlePlaceOrder = () => {
    if (!defaultAddress) {
      showToast('Please select or add a delivery address', 'err');
      return;
    }
    if (cart.length === 0) {
      showToast('Cart is empty', 'err');
      return;
    }

    const orderId = String(Math.floor(10000000 + Math.random() * 90000000));
    setPendingOrderNum(orderId);

    if (paymentMethod === 'COD') {
      const newOrder: Order = {
        order_num: orderId,
        meesho_order_num: `MSH-${orderId}`,
        items_text: cart.map(i => `${i.name} x${i.qty}`).join(', '),
        total: codAmount,
        status: 'pending',
        payment_method: 'COD',
        created_at: Date.now(),
        address: `${defaultAddress.address_line_1}, ${defaultAddress.city}`
      };
      setOrders(prev => [newOrder, ...prev]);
      setLastPlacedOrder(newOrder);
      setCart([]);
      setShowCheckoutSheet(false);
      showToast('Order Placed with COD ✓', 'ok');
    } else {
      // UPI with Juspay WAPI intent URL generator
      const amtStr = `${floatNumber(upiAmount).toFixed(2)}`;
      const upiUrl = `upi://pay?pa=MEESHOONLINEPG@axl&pn=MEESHO%20TECHNOLOGIES%20PRIVATE%20LIMITED&am=${amtStr}&mam=${amtStr}&tr=${orderId}&tn=UPI%20Intent&mc=5262&mode=04&purpose=00&cu=INR&utm_source=${orderId}`;
      setCurrentUpiUri(upiUrl);
      setShowCheckoutSheet(false);
      setShowQrModal(true);
    }
  };

  const handleConfirmUpiPaid = () => {
    const newOrder: Order = {
      order_num: pendingOrderNum,
      meesho_order_num: `MSH-${pendingOrderNum}`,
      items_text: cart.map(i => `${i.name} x${i.qty}`).join(', '),
      total: upiAmount,
      status: 'confirmed',
      payment_method: 'UPI',
      created_at: Date.now(),
      address: defaultAddress ? `${defaultAddress.address_line_1}, ${defaultAddress.city}` : ''
    };
    setOrders(prev => [newOrder, ...prev]);
    setLastPlacedOrder(newOrder);
    setCart([]);
    setShowQrModal(false);
    showToast('UPI Payment Confirmed! Order placed.', 'ok');
  };

  const floatNumber = (n: number) => Number(n) || 0;

  return (
    <div className="min-h-screen bg-[#0B0C10] text-[#EDF2F7] max-w-[480px] mx-auto pb-24 relative selection:bg-[#66FCF1]/30">
      {/* Toast Notification */}
      {toastMsg && (
        <div
          className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-full text-xs font-bold tracking-wide transition-all shadow-xl backdrop-blur-md border ${
            toastMsg.kind === 'err'
              ? 'bg-[#1F1722]/95 text-[#FF5C7A] border-[#FF5C7A]/50 shadow-[#FF5C7A]/20'
              : 'bg-[#142323]/95 text-[#3DDC97] border-[#3DDC97]/50 shadow-[#3DDC97]/20'
          }`}
        >
          {toastMsg.text}
        </div>
      )}

      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-[#0B0C10]/85 backdrop-blur-md border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#66FCF1] to-[#45A29E] flex items-center justify-center text-[#0B0C10] font-black text-base shadow-[0_0_15px_rgba(102,252,241,0.5)]">
            ⚡
          </div>
          <div>
            <h1 className="text-sm font-extrabold tracking-tight flex items-center gap-1.5">
              FOD PILOT
              <span className="text-[10px] bg-[#66FCF1]/10 text-[#66FCF1] px-1.5 py-0.5 rounded-md font-mono">
                ENGINE
              </span>
            </h1>
            <p className="text-[9px] font-semibold text-[#9AA7B8] tracking-wider uppercase">
              VIEDDETX SINGH
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-[10px] font-mono font-bold text-[#66FCF1] bg-[#66FCF1]/10 border border-[#66FCF1]/30 px-2.5 py-1 rounded-full">
            ID {userId.slice(-6)}
          </div>
          <button
            onClick={() => setTab('cart')}
            className="relative w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center active:scale-95 transition-transform"
          >
            <ShoppingCart className="w-4 h-4 text-[#EDF2F7]" />
            {cart.length > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-[#C9338A] text-white text-[10px] font-black flex items-center justify-center px-1 shadow-[0_0_10px_rgba(201,51,138,0.8)]">
                {cart.reduce((a, b) => a + b.qty, 0)}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Main Content Area by Tabs */}
      <main className="px-3.5 pt-3.5 space-y-4">
        {/* ===================== HOME TAB ===================== */}
        {tab === 'home' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            {/* FOD Offer Card */}
            <div className="relative overflow-hidden rounded-3xl p-5 bg-gradient-to-br from-[#66FCF1]/15 via-white/[0.04] to-[#C9338A]/15 border border-[#66FCF1]/30 shadow-[0_10px_40px_rgba(0,0,0,0.5)]">
              <div className="absolute -right-16 -top-16 w-52 h-52 rounded-full bg-[#66FCF1]/20 blur-3xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold tracking-widest text-[#66FCF1] uppercase flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5" /> First-Order Engine
                </span>
                <span className="text-[10px] font-mono font-bold text-[#FFC94D] bg-[#FFC94D]/10 border border-[#FFC94D]/30 px-2 py-0.5 rounded-full">
                  BUCKET {offer.bucket}
                </span>
              </div>

              <div className="my-2.5">
                <div className="text-4xl font-extrabold font-['Space_Grotesk'] tracking-tight bg-gradient-to-r from-white via-[#66FCF1] to-[#45A29E] bg-clip-text text-transparent">
                  {offer.display_text}
                </div>
                <p className="text-xs font-medium text-[#9AA7B8] mt-1">
                  {offer.subtitle} • Automatically applies on first checkout
                </p>
              </div>

              <div className="flex items-center gap-2.5 mt-4">
                <button
                  onClick={handleRollFOD}
                  disabled={isRolling}
                  className="flex-1 py-3 px-4 rounded-xl font-extrabold text-xs tracking-wide bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_4px_20px_rgba(102,252,241,0.35)] active:scale-95 transition-all flex items-center justify-center gap-1.5"
                >
                  🎲 {isRolling ? 'Rolling…' : 'Roll for Best Offer'}
                </button>
                <button
                  onClick={() => {
                    setTab('search');
                    showToast('Explore items to redeem your discount', 'ok');
                  }}
                  className="py-3 px-4 rounded-xl font-bold text-xs bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all text-[#EDF2F7]"
                >
                  Use Offer →
                </button>
              </div>
            </div>

            {/* Account & Orders Mini Stat Badges */}
            <div className="grid grid-cols-3 gap-2.5">
              <div
                onClick={() => setTab('account')}
                className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/10 text-center cursor-pointer active:scale-95 transition-transform"
              >
                <div className="text-lg font-bold font-['Space_Grotesk'] text-[#66FCF1]">
                  {isLinked ? `+91 ${linkedPhone.slice(-4)}` : 'Guest'}
                </div>
                <span className="text-[9.5px] font-bold text-[#9AA7B8] tracking-wider uppercase">
                  ACCOUNT
                </span>
              </div>
              <div
                onClick={() => setTab('cart')}
                className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/10 text-center cursor-pointer active:scale-95 transition-transform"
              >
                <div className="text-lg font-bold font-['Space_Grotesk'] text-[#FF7EB3]">
                  {cart.reduce((a, b) => a + b.qty, 0)}
                </div>
                <span className="text-[9.5px] font-bold text-[#9AA7B8] tracking-wider uppercase">
                  IN CART
                </span>
              </div>
              <div
                onClick={() => setTab('account')}
                className="p-3.5 rounded-2xl bg-white/[0.03] border border-white/10 text-center cursor-pointer active:scale-95 transition-transform"
              >
                <div className="text-lg font-bold font-['Space_Grotesk'] text-[#3DDC97]">
                  {orders.length}
                </div>
                <span className="text-[9.5px] font-bold text-[#9AA7B8] tracking-wider uppercase">
                  ORDERS
                </span>
              </div>
            </div>

            {/* Trending Products Header */}
            <div className="flex items-center justify-between pt-1">
              <h2 className="text-xs font-extrabold tracking-widest text-[#9AA7B8] uppercase flex items-center gap-2">
                <span>TRENDING DISCOUNTS</span>
              </h2>
              <button
                onClick={() => setTab('search')}
                className="text-[11px] font-bold text-[#66FCF1] flex items-center gap-1 hover:underline"
              >
                View all <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {/* 2-Column Product Grid */}
            <div className="grid grid-cols-2 gap-3">
              {products.slice(0, 4).map(product => (
                <div
                  key={product.product_id}
                  onClick={() => {
                    setSelectedProduct(product);
                    setSelectedSizeId(product.sizes?.[0]?.id || 0);
                  }}
                  className="rounded-2xl overflow-hidden bg-white/[0.04] border border-white/10 hover:border-[#66FCF1]/40 transition-all cursor-pointer group active:scale-[0.97]"
                >
                  <div className="aspect-square relative overflow-hidden bg-[#151C28]">
                    <img
                      src={product.image}
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    {product.fod_savings && (
                      <span className="absolute bottom-2 left-2 text-[9.5px] font-black text-[#0B0C10] bg-gradient-to-r from-[#66FCF1] to-[#98FFF6] px-2 py-0.5 rounded-full shadow-lg">
                        {product.fod_savings}
                      </span>
                    )}
                  </div>
                  <div className="p-2.5 space-y-1">
                    <p className="text-xs font-semibold line-clamp-2 text-[#DFE7F2] leading-snug">
                      {product.name}
                    </p>
                    <div className="flex items-baseline gap-1.5 flex-wrap pt-0.5">
                      <span className="text-sm font-bold font-['Space_Grotesk'] text-white">
                        ₹{product.price}
                      </span>
                      {product.original_price > product.price && (
                        <span className="text-[11px] line-through text-[#5C6B80]">
                          ₹{product.original_price}
                        </span>
                      )}
                      <span className="text-[10px] font-extrabold text-[#3DDC97]">
                        {product.discount_text}
                      </span>
                    </div>
                    <div className="text-[10px] font-semibold text-[#FFC94D]">
                      ★ {product.rating?.average || '4.2'} ({product.rating?.count || 450})
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===================== SEARCH TAB ===================== */}
        {tab === 'search' && (
          <div className="space-y-3.5 animate-in fade-in duration-200">
            {/* Search Input Bar */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5C6B80]" />
                <input
                  type="text"
                  placeholder="Search kurti, saree, tshirt, shoes..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3.5 py-3 rounded-2xl bg-white/[0.06] border border-white/10 text-sm text-[#EDF2F7] focus:outline-none focus:border-[#66FCF1] transition-colors"
                />
              </div>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="px-3 rounded-2xl bg-white/5 border border-white/10 text-xs font-bold text-[#9AA7B8]"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Quick Chips */}
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
              {['kurti', 'saree', 'tshirt', 'smartwatch', 'shoes', 'necklace', 'handbag'].map(chip => (
                <button
                  key={chip}
                  onClick={() => setSearchQuery(chip)}
                  className="flex-none px-3.5 py-1.5 rounded-full text-xs font-bold text-[#66FCF1] bg-[#66FCF1]/10 border border-[#66FCF1]/30 hover:bg-[#66FCF1]/20 active:scale-95 transition-all"
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Search Results in 2-Column Grid */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              {filteredProducts.map(product => (
                <div
                  key={product.product_id}
                  onClick={() => {
                    setSelectedProduct(product);
                    setSelectedSizeId(product.sizes?.[0]?.id || 0);
                  }}
                  className="rounded-2xl overflow-hidden bg-white/[0.04] border border-white/10 hover:border-[#66FCF1]/40 transition-all cursor-pointer group active:scale-[0.97]"
                >
                  <div className="aspect-square relative overflow-hidden bg-[#151C28]">
                    <img
                      src={product.image}
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    {product.fod_savings && (
                      <span className="absolute bottom-2 left-2 text-[9.5px] font-black text-[#0B0C10] bg-gradient-to-r from-[#66FCF1] to-[#98FFF6] px-2 py-0.5 rounded-full shadow-lg">
                        {product.fod_savings}
                      </span>
                    )}
                  </div>
                  <div className="p-2.5 space-y-1">
                    <p className="text-xs font-semibold line-clamp-2 text-[#DFE7F2] leading-snug">
                      {product.name}
                    </p>
                    <div className="flex items-baseline gap-1.5 flex-wrap pt-0.5">
                      <span className="text-sm font-bold font-['Space_Grotesk'] text-white">
                        ₹{product.price}
                      </span>
                      {product.original_price > product.price && (
                        <span className="text-[11px] line-through text-[#5C6B80]">
                          ₹{product.original_price}
                        </span>
                      )}
                      <span className="text-[10px] font-extrabold text-[#3DDC97]">
                        {product.discount_text}
                      </span>
                    </div>
                    <div className="text-[10px] font-semibold text-[#FFC94D]">
                      ★ {product.rating?.average || '4.2'} ({product.rating?.count || 450})
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===================== CART TAB ===================== */}
        {tab === 'cart' && (
          <div className="space-y-3.5 animate-in fade-in duration-200">
            {/* Delivery Address Chip */}
            <div
              onClick={() => setShowAddressSheet(true)}
              className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.04] border border-white/10 cursor-pointer active:scale-[0.98] transition-transform"
            >
              <div className="w-8 h-8 rounded-xl bg-[#66FCF1]/10 text-[#66FCF1] flex items-center justify-center flex-none">
                <MapPin className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-white truncate">
                  {defaultAddress ? `${defaultAddress.name} • ${defaultAddress.pin}` : 'Select Delivery Address'}
                </p>
                <p className="text-[11px] text-[#9AA7B8] truncate">
                  {defaultAddress ? `${defaultAddress.address_line_1}, ${defaultAddress.city}` : 'Tap to add or select destination'}
                </p>
              </div>
              <span className="text-xs font-extrabold text-[#66FCF1]">Change</span>
            </div>

            {/* Cart Items List */}
            {cart.length === 0 ? (
              <div className="text-center py-16 space-y-3 bg-white/[0.02] border border-white/5 rounded-3xl">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-white/5 flex items-center justify-center text-2xl">
                  🛒
                </div>
                <h3 className="text-sm font-bold text-white">Your Cart is Empty</h3>
                <p className="text-xs text-[#9AA7B8]">Find items in search and apply first-order discounts</p>
                <button
                  onClick={() => setTab('search')}
                  className="px-5 py-2.5 rounded-xl font-bold text-xs bg-[#66FCF1] text-[#0B0C10]"
                >
                  Start Shopping
                </button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {cart.map((item, idx) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 p-3 rounded-2xl bg-white/[0.04] border border-white/10"
                  >
                    <img
                      src={item.image}
                      alt={item.name}
                      className="w-16 h-16 rounded-xl object-cover bg-[#151C28] flex-none"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-white truncate">{item.name}</p>
                      <p className="text-[11px] text-[#9AA7B8]">Size: {item.variation_name || 'Free Size'}</p>
                      <div className="flex items-baseline gap-1.5 mt-1 font-['Space_Grotesk']">
                        <span className="text-sm font-bold text-white">₹{item.price}</span>
                        {item.mrp > item.price && (
                          <span className="text-xs line-through text-[#5C6B80]">₹{item.mrp}</span>
                        )}
                      </div>
                    </div>

                    {/* Quantity Controls: ONLY + and Delete (No decrease button) */}
                    <div className="flex items-center gap-2 flex-none">
                      <button
                        onClick={() => handleDeleteItem(idx)}
                        className="w-7 h-7 rounded-full bg-[#FF5C7A]/15 text-[#FF5C7A] border border-[#FF5C7A]/30 flex items-center justify-center active:scale-90 transition-transform"
                        title="Delete item"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <span className="font-['Space_Grotesk'] font-bold text-xs min-w-[20px] text-center">
                        ×{item.qty}
                      </span>
                      <button
                        onClick={() => handleIncreaseQty(idx)}
                        className="w-7 h-7 rounded-full bg-[#66FCF1]/15 text-[#66FCF1] border border-[#66FCF1]/30 flex items-center justify-center active:scale-90 transition-transform"
                        title="Increase quantity"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}

                {/* Cart Price Breakdown Summary */}
                <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/10 space-y-2">
                  <div className="flex justify-between text-xs text-[#9AA7B8]">
                    <span>Product Price (MRP)</span>
                    <span className="font-['Space_Grotesk'] text-white">₹{productPrice}</span>
                  </div>
                  <div className="flex justify-between text-xs text-[#3DDC97]">
                    <span>Total Discounts (FOD + Promo)</span>
                    <span className="font-['Space_Grotesk'] font-bold">−₹{totalDiscounts}</span>
                  </div>
                  <div className="pt-2 border-t border-dashed border-white/10 flex justify-between text-sm font-bold text-white">
                    <span>Order Total</span>
                    <span className="font-['Space_Grotesk'] text-base">₹{codAmount}</span>
                  </div>

                  {/* COD vs UPI Comparison */}
                  <div className="grid grid-cols-2 gap-2.5 pt-2">
                    <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/10 text-center">
                      <span className="text-[9px] font-extrabold text-[#9AA7B8] uppercase block">
                        CASH ON DELIVERY
                      </span>
                      <span className="text-sm font-bold font-['Space_Grotesk'] text-white">
                        ₹{codAmount}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-xl bg-[#3DDC97]/5 border border-[#3DDC97]/30 text-center">
                      <span className="text-[9px] font-extrabold text-[#3DDC97] uppercase block">
                        PAY VIA UPI (SAVE ₹{upiPrepaidDiscount})
                      </span>
                      <span className="text-sm font-bold font-['Space_Grotesk'] text-[#3DDC97]">
                        ₹{upiAmount}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Continue to Checkout Button */}
                <button
                  onClick={() => setShowCheckoutSheet(true)}
                  className="w-full py-3.5 rounded-2xl font-extrabold text-sm tracking-wide bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_6px_25px_rgba(102,252,241,0.35)] active:scale-95 transition-all flex items-center justify-center gap-2"
                >
                  Proceed to Checkout • ₹{paymentMethod === 'COD' ? codAmount : upiAmount}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ===================== ACCOUNT TAB ===================== */}
        {tab === 'account' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            {/* Account Status Card */}
            <div className="p-4 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-[#C9338A] to-[#801B52] flex items-center justify-center text-xl shadow-[0_0_20px_rgba(201,51,138,0.4)]">
                👤
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">
                    {isLinked ? `+91 ${linkedPhone}` : 'No Linked Account'}
                  </span>
                  <span
                    className={`text-[9px] font-extrabold px-2 py-0.5 rounded-full ${
                      isLinked
                        ? 'bg-[#3DDC97]/10 text-[#3DDC97] border border-[#3DDC97]/30'
                        : 'bg-white/10 text-[#9AA7B8]'
                    }`}
                  >
                    {isLinked ? 'SESSION ACTIVE' : 'DISCONNECTED'}
                  </span>
                </div>
                <p className="text-[11px] text-[#9AA7B8] font-mono mt-0.5">
                  UID: {isLinked ? linkedUid : '—'} • FOD Ready
                </p>
              </div>
            </div>

            {/* OTP Login Section */}
            <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/10 space-y-3">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[#66FCF1]" />
                <h3 className="text-xs font-bold text-white tracking-wide uppercase">
                  Mobile OTP Authentication
                </h3>
              </div>
              <p className="text-xs text-[#9AA7B8]">
                Log in via real-time Meesho OTP sent directly to WhatsApp or SMS
              </p>

              <div className="space-y-2">
                <input
                  type="tel"
                  maxLength={10}
                  placeholder="10-digit mobile number"
                  value={otpPhone}
                  onChange={e => setOtpPhone(e.target.value.replace(/\D/g, ''))}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
                />
                {!otpSent ? (
                  <button
                    onClick={() => {
                      if (otpPhone.length !== 10) {
                        showToast('Enter valid 10-digit phone', 'err');
                        return;
                      }
                      setOtpSent(true);
                      showToast('OTP sent to your number ✓', 'ok');
                    }}
                    className="w-full py-2.5 rounded-xl text-xs font-bold bg-[#66FCF1] text-[#0B0C10] active:scale-95 transition-all"
                  >
                    Send OTP Code
                  </button>
                ) : (
                  <div className="space-y-2">
                    <input
                      type="text"
                      maxLength={6}
                      placeholder="Enter 6-digit OTP"
                      value={otpCode}
                      onChange={e => setOtpCode(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#3DDC97]"
                    />
                    <button
                      onClick={() => {
                        if (otpCode.length < 4) {
                          showToast('Enter the OTP received', 'err');
                          return;
                        }
                        setIsLinked(true);
                        setLinkedPhone(otpPhone);
                        setLinkedUid(String(Math.floor(1000000 + Math.random() * 9000000)));
                        setOtpSent(false);
                        setOtpCode('');
                        showToast('Account Connected via OTP ✓', 'ok');
                      }}
                      className="w-full py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-[#C9338A] to-[#FF7EB3] text-white active:scale-95 transition-all"
                    >
                      Verify &amp; Link Account
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* JSON Session Login Section */}
            <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/10 space-y-3">
              <div className="flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-[#C9338A]" />
                <h3 className="text-xs font-bold text-white tracking-wide uppercase">
                  Session JSON Import
                </h3>
              </div>
              <p className="text-xs text-[#9AA7B8]">
                Paste existing Meesho session JSON containing user_id, xo token, and instance_id
              </p>
              <textarea
                rows={3}
                placeholder='{"user_id":"7428192","xo":"...","instance_id":"..."}'
                value={jsonInput}
                onChange={e => setJsonInput(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs font-mono text-white focus:outline-none focus:border-[#C9338A]"
              />
              <button
                onClick={() => {
                  try {
                    const parsed = JSON.parse(jsonInput);
                    if (parsed.user_id && (parsed.xo || parsed.token)) {
                      setIsLinked(true);
                      setLinkedUid(String(parsed.user_id));
                      setJsonInput('');
                      showToast('Session JSON Linked Successfully ✓', 'ok');
                    } else {
                      showToast('JSON must include user_id and xo', 'err');
                    }
                  } catch {
                    showToast('Invalid JSON syntax', 'err');
                  }
                }}
                className="w-full py-2.5 rounded-xl text-xs font-bold bg-white/10 hover:bg-white/15 text-white active:scale-95 transition-all"
              >
                Connect Session JSON
              </button>
            </div>

            {/* Order History */}
            <div className="space-y-2.5 pt-2">
              <h3 className="text-xs font-bold text-[#9AA7B8] uppercase tracking-wider">
                Order History ({orders.length})
              </h3>
              {orders.length === 0 ? (
                <div className="p-6 text-center text-xs text-[#9AA7B8] bg-white/[0.02] rounded-2xl border border-white/5">
                  No orders placed yet
                </div>
              ) : (
                orders.map(order => (
                  <div
                    key={order.order_num}
                    className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/10 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-white">
                        #{order.order_num}
                      </span>
                      <span className="text-[9.5px] font-extrabold px-2 py-0.5 rounded-full bg-[#3DDC97]/10 text-[#3DDC97] border border-[#3DDC97]/30 uppercase">
                        {order.status}
                      </span>
                    </div>
                    <p className="text-xs text-[#DFE7F2] line-clamp-1">{order.items_text}</p>
                    <div className="flex items-center justify-between text-xs pt-1">
                      <span className="text-[11px] text-[#9AA7B8]">{order.payment_method}</span>
                      <span className="font-bold font-['Space_Grotesk'] text-white">₹{order.total}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>

      {/* ===================== PRODUCT DETAIL BOTTOM SHEET ===================== */}
      {selectedProduct && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end justify-center animate-in fade-in duration-200"
          onClick={() => setSelectedProduct(null)}
        >
          <div
            className="w-full max-w-[480px] max-h-[85vh] overflow-y-auto bg-[#141A26] rounded-t-3xl p-5 border-t border-white/10 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-white/20 rounded-full mx-auto" />
            <div className="flex items-start gap-3">
              <img
                src={selectedProduct.image}
                alt={selectedProduct.name}
                className="w-24 h-24 rounded-2xl object-cover bg-[#151C28] flex-none"
              />
              <div className="flex-1 min-w-0 space-y-1">
                <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug">
                  {selectedProduct.name}
                </h3>
                <div className="flex items-baseline gap-2 font-['Space_Grotesk']">
                  <span className="text-xl font-extrabold text-white">
                    ₹{selectedProduct.price}
                  </span>
                  {selectedProduct.original_price > selectedProduct.price && (
                    <span className="text-xs line-through text-[#5C6B80]">
                      ₹{selectedProduct.original_price}
                    </span>
                  )}
                </div>
                {selectedProduct.fod_savings && (
                  <span className="inline-block text-[10px] font-black text-[#0B0C10] bg-[#66FCF1] px-2 py-0.5 rounded-full">
                    {selectedProduct.fod_savings}
                  </span>
                )}
              </div>
            </div>

            {/* Sizes Selection */}
            <div>
              <p className="text-xs font-bold text-[#9AA7B8] mb-2 uppercase tracking-wider">
                Select Variation / Size
              </p>
              <div className="flex flex-wrap gap-2">
                {selectedProduct.sizes?.map(size => (
                  <button
                    key={size.id}
                    onClick={() => setSelectedSizeId(size.id)}
                    className={`px-4 py-2 rounded-full text-xs font-bold transition-all ${
                      selectedSizeId === size.id
                        ? 'bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_0_12px_rgba(102,252,241,0.4)]'
                        : 'bg-white/5 text-[#EDF2F7] border border-white/10'
                    }`}
                  >
                    {size.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Add to Cart / Buy Now Action Buttons */}
            <div className="flex gap-2.5 pt-2">
              <button
                onClick={() => handleAddToCart(selectedProduct, false)}
                className="flex-1 py-3.5 rounded-2xl font-bold text-xs bg-white/5 border border-white/10 text-white active:scale-95 transition-all"
              >
                Add to Cart
              </button>
              <button
                onClick={() => handleAddToCart(selectedProduct, true)}
                className="flex-1 py-3.5 rounded-2xl font-extrabold text-xs bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_4px_20px_rgba(102,252,241,0.35)] active:scale-95 transition-all"
              >
                Buy Now →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================== CHECKOUT BOTTOM SHEET ===================== */}
      {showCheckoutSheet && (
        <div
          className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-end justify-center animate-in fade-in duration-200"
          onClick={() => setShowCheckoutSheet(false)}
        >
          <div
            className="w-full max-w-[480px] max-h-[90vh] overflow-y-auto bg-[#141A26] rounded-t-3xl p-5 border-t border-white/10 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-white/20 rounded-full mx-auto" />
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-white">Order Checkout</h3>
              <button
                onClick={() => setShowCheckoutSheet(false)}
                className="text-[#9AA7B8] hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Delivery Destination */}
            <div className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/10">
              <span className="text-[10px] font-extrabold text-[#9AA7B8] uppercase tracking-wider block mb-1">
                DELIVER TO
              </span>
              <p className="text-xs font-bold text-white">
                {defaultAddress?.name} ({defaultAddress?.mobile})
              </p>
              <p className="text-xs text-[#9AA7B8] mt-0.5">
                {defaultAddress?.address_line_1}, {defaultAddress?.city} — {defaultAddress?.pin}
              </p>
            </div>

            {/* 4-Step Checkout Protocol Pipeline */}
            <div className="p-3 rounded-2xl bg-white/[0.02] border border-white/5 space-y-1.5 text-[10px] font-mono text-[#9AA7B8]">
              <div className="text-[9.5px] font-bold text-[#66FCF1] uppercase tracking-wider">
                EXECUTION FLOW (CHECKOUT_METHOD.TXT)
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#3DDC97]">✓ 1.</span> POST /api/1.0/cart/location (bind dest_pin)
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#3DDC97]">✓ 2.</span> POST /api/8.0/cart (refresh review totals)
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#3DDC97]">✓ 3.</span> POST /api/1.0/cart/paymentinfo (apply discount)
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[#66FCF1]">→ 4.</span> POST /api/4.0/preorders (place order)
              </div>
            </div>

            {/* Payment Method Selector */}
            <div className="space-y-2">
              <span className="text-[10px] font-extrabold text-[#9AA7B8] uppercase tracking-wider">
                SELECT PAYMENT MODE
              </span>

              {/* COD Option */}
              <div
                onClick={() => setPaymentMethod('COD')}
                className={`flex items-center justify-between p-3.5 rounded-2xl border cursor-pointer transition-all ${
                  paymentMethod === 'COD'
                    ? 'bg-[#66FCF1]/10 border-[#66FCF1] shadow-[0_0_15px_rgba(102,252,241,0.15)]'
                    : 'bg-white/[0.03] border-white/10'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      paymentMethod === 'COD' ? 'border-[#66FCF1]' : 'border-white/30'
                    }`}
                  >
                    {paymentMethod === 'COD' && <div className="w-2 h-2 rounded-full bg-[#66FCF1]" />}
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white">💵 Cash on Delivery (COD)</p>
                    <p className="text-[11px] text-[#9AA7B8]">Pay upon delivery at your doorstep</p>
                  </div>
                </div>
                <span className="font-['Space_Grotesk'] font-bold text-sm text-white">
                  ₹{codAmount}
                </span>
              </div>

              {/* UPI Option */}
              <div
                onClick={() => setPaymentMethod('UPI')}
                className={`flex items-center justify-between p-3.5 rounded-2xl border cursor-pointer transition-all ${
                  paymentMethod === 'UPI'
                    ? 'bg-[#3DDC97]/10 border-[#3DDC97] shadow-[0_0_15px_rgba(61,220,151,0.15)]'
                    : 'bg-white/[0.03] border-white/10'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      paymentMethod === 'UPI' ? 'border-[#3DDC97]' : 'border-white/30'
                    }`}
                  >
                    {paymentMethod === 'UPI' && <div className="w-2 h-2 rounded-full bg-[#3DDC97]" />}
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white flex items-center gap-1.5">
                      ⚡ Pay Online via UPI
                      <span className="text-[9px] bg-[#3DDC97]/20 text-[#3DDC97] px-1.5 py-0.2 rounded font-bold">
                        SAVE ₹{upiPrepaidDiscount}
                      </span>
                    </p>
                    <p className="text-[11px] text-[#9AA7B8]">Instant confirmation with Juspay QR</p>
                  </div>
                </div>
                <span className="font-['Space_Grotesk'] font-bold text-sm text-[#3DDC97]">
                  ₹{upiAmount}
                </span>
              </div>
            </div>

            {/* Confirm & Place Order Button */}
            <button
              onClick={handlePlaceOrder}
              className="w-full py-3.5 rounded-2xl font-extrabold text-sm bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_4px_25px_rgba(102,252,241,0.35)] active:scale-95 transition-all"
            >
              Confirm &amp; Place Order • ₹{effectiveTotal}
            </button>
          </div>
        </div>
      )}

      {/* ===================== ADDRESS PICKER SHEET ===================== */}
      {showAddressSheet && (
        <div
          className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-end justify-center animate-in fade-in duration-200"
          onClick={() => setShowAddressSheet(false)}
        >
          <div
            className="w-full max-w-[480px] max-h-[90vh] overflow-y-auto bg-[#141A26] rounded-t-3xl p-5 border-t border-white/10 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-white/20 rounded-full mx-auto" />
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-extrabold text-white">Delivery Addresses</h3>
              <button
                onClick={() => setShowAddressSheet(false)}
                className="text-[#9AA7B8] hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* List Existing Addresses */}
            <div className="space-y-2">
              {addresses.map(a => (
                <div
                  key={a.id}
                  onClick={() => {
                    setAddresses(prev => prev.map(x => ({ ...x, is_default: x.id === a.id })));
                    setShowAddressSheet(false);
                    showToast('Address Selected ✓', 'ok');
                  }}
                  className={`p-3 rounded-2xl border cursor-pointer transition-all ${
                    a.is_default
                      ? 'bg-[#66FCF1]/10 border-[#66FCF1]'
                      : 'bg-white/[0.03] border-white/10'
                  }`}
                >
                  <p className="text-xs font-bold text-white">
                    {a.name} • {a.mobile}
                  </p>
                  <p className="text-xs text-[#9AA7B8] mt-0.5">
                    {a.address_line_1}, {a.city} — {a.pin}
                  </p>
                </div>
              ))}
            </div>

            {/* Add New Address Form */}
            <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/10 space-y-2.5">
              <span className="text-[10px] font-extrabold text-[#9AA7B8] uppercase tracking-wider block">
                ADD NEW ADDRESS
              </span>
              <input
                type="text"
                placeholder="Full Name"
                value={newAddress.name}
                onChange={e => setNewAddress({ ...newAddress, name: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
              />
              <input
                type="tel"
                maxLength={10}
                placeholder="10-digit Mobile Number"
                value={newAddress.mobile}
                onChange={e => setNewAddress({ ...newAddress, mobile: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
              />

              {/* Geolocation Detect Location Button */}
              <button
                onClick={handleDetectLocation}
                disabled={isDetectingLocation}
                className="w-full py-2.5 rounded-xl font-bold text-xs bg-[#66FCF1]/10 border border-[#66FCF1]/30 text-[#66FCF1] flex items-center justify-center gap-1.5 active:scale-95 transition-all"
              >
                <Navigation className="w-3.5 h-3.5" />
                {isDetectingLocation ? 'Detecting GPS...' : '📍 Detect Location (Auto-fill city/pin)'}
              </button>

              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Pincode"
                  value={newAddress.pin}
                  onChange={e => setNewAddress({ ...newAddress, pin: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
                />
                <input
                  type="text"
                  placeholder="City"
                  value={newAddress.city}
                  onChange={e => setNewAddress({ ...newAddress, city: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
                />
              </div>

              <input
                type="text"
                placeholder="House No., Street, Colony"
                value={newAddress.address_line_1}
                onChange={e => setNewAddress({ ...newAddress, address_line_1: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-white/[0.06] border border-white/10 text-xs text-white focus:outline-none focus:border-[#66FCF1]"
              />

              <button
                onClick={handleSaveAddress}
                className="w-full py-2.5 rounded-xl font-bold text-xs bg-[#66FCF1] text-[#0B0C10] active:scale-95 transition-all"
              >
                Save &amp; Select
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================== JUSPAY UPI QR MODAL ===================== */}
      {showQrModal && (
        <div
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => setShowQrModal(false)}
        >
          <div
            className="w-full max-w-[340px] rounded-3xl p-6 bg-gradient-to-b from-[#192233] to-[#111722] border border-[#66FCF1]/30 shadow-[0_0_50px_rgba(102,252,241,0.2)] text-center space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div>
              <span className="text-[10px] font-extrabold tracking-widest text-[#66FCF1] uppercase">
                JUSPAY UPI PAYMENT
              </span>
              <div className="text-3xl font-extrabold font-['Space_Grotesk'] text-white mt-1">
                ₹{upiAmount}
              </div>
              <p className="text-[11px] text-[#9AA7B8] font-mono">Order #{pendingOrderNum}</p>
            </div>

            {/* Generated QR Code Card */}
            <div className="w-52 h-52 mx-auto rounded-2xl bg-white p-2.5 shadow-xl flex items-center justify-center">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=4&data=${encodeURIComponent(
                  currentUpiUri
                )}`}
                alt="UPI QR Code"
                className="w-full h-full object-contain"
              />
            </div>

            {/* VPA Copy Chip */}
            <div className="flex items-center justify-center gap-2 text-xs text-[#66FCF1] font-mono font-bold bg-[#66FCF1]/10 border border-[#66FCF1]/20 py-1.5 px-3 rounded-full">
              <span>MEESHOONLINEPG@axl</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText('MEESHOONLINEPG@axl');
                  showToast('Merchant VPA Copied ✓', 'ok');
                }}
                className="hover:scale-110 active:scale-95 transition-transform"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2">
              <a
                href={currentUpiUri}
                target="_blank"
                rel="noreferrer"
                className="w-full py-3 rounded-xl font-bold text-xs bg-white/10 hover:bg-white/15 text-white flex items-center justify-center gap-1.5 transition-all"
              >
                Open UPI App <ExternalLink className="w-3.5 h-3.5" />
              </a>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(currentUpiUri);
                  showToast('UPI Link Copied to Clipboard ✓', 'ok');
                }}
                className="w-full py-2.5 rounded-xl font-bold text-xs bg-white/5 border border-white/10 text-[#9AA7B8] hover:text-white"
              >
                Copy UPI Intent Link
              </button>
              <button
                onClick={handleConfirmUpiPaid}
                className="w-full py-3.5 rounded-xl font-extrabold text-xs bg-gradient-to-r from-[#66FCF1] to-[#45A29E] text-[#0B0C10] shadow-[0_4px_20px_rgba(102,252,241,0.3)] active:scale-95 transition-all"
              >
                ✅ I have paid
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================== SUCCESS ORDER SHEET ===================== */}
      {lastPlacedOrder && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => setLastPlacedOrder(null)}
        >
          <div
            className="w-full max-w-[340px] rounded-3xl p-6 bg-[#141A26] border border-[#3DDC97]/40 shadow-[0_0_40px_rgba(61,220,151,0.2)] text-center space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="w-16 h-16 rounded-full bg-[#3DDC97]/15 border border-[#3DDC97]/40 mx-auto flex items-center justify-center text-3xl text-[#3DDC97]">
              ✓
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Order Confirmed!</h3>
              <p className="text-xs text-[#9AA7B8] font-mono mt-0.5">
                ID #{lastPlacedOrder.order_num}
              </p>
              <div className="text-2xl font-extrabold font-['Space_Grotesk'] text-white mt-2">
                ₹{lastPlacedOrder.total}
              </div>
              <p className="text-xs text-[#3DDC97] font-semibold mt-1">
                Payment: {lastPlacedOrder.payment_method}
              </p>
            </div>

            <button
              onClick={() => {
                setLastPlacedOrder(null);
                setTab('account');
              }}
              className="w-full py-3 rounded-xl font-extrabold text-xs bg-[#3DDC97] text-[#0B0C10] active:scale-95 transition-all"
            >
              View in Orders
            </button>
          </div>
        </div>
      )}

      {/* ===================== BOTTOM NAVIGATION TABS ===================== */}
      <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] z-40 flex items-center justify-around py-2.5 px-3 bg-[#0B0C10]/90 backdrop-blur-xl border-t border-white/10">
        <button
          onClick={() => setTab('home')}
          className={`flex flex-col items-center gap-1 text-[10px] font-extrabold tracking-wider transition-colors ${
            tab === 'home' ? 'text-[#66FCF1] drop-shadow-[0_0_8px_rgba(102,252,241,0.8)]' : 'text-[#5C6B80]'
          }`}
        >
          <ShoppingBag className="w-5 h-5" />
          HOME
        </button>

        <button
          onClick={() => setTab('search')}
          className={`flex flex-col items-center gap-1 text-[10px] font-extrabold tracking-wider transition-colors ${
            tab === 'search' ? 'text-[#66FCF1] drop-shadow-[0_0_8px_rgba(102,252,241,0.8)]' : 'text-[#5C6B80]'
          }`}
        >
          <Search className="w-5 h-5" />
          SEARCH
        </button>

        <button
          onClick={() => setTab('cart')}
          className={`relative flex flex-col items-center gap-1 text-[10px] font-extrabold tracking-wider transition-colors ${
            tab === 'cart' ? 'text-[#66FCF1] drop-shadow-[0_0_8px_rgba(102,252,241,0.8)]' : 'text-[#5C6B80]'
          }`}
        >
          <ShoppingCart className="w-5 h-5" />
          CART
          {cart.length > 0 && (
            <span className="absolute -top-1 right-1 w-2 h-2 rounded-full bg-[#C9338A]" />
          )}
        </button>

        <button
          onClick={() => setTab('account')}
          className={`flex flex-col items-center gap-1 text-[10px] font-extrabold tracking-wider transition-colors ${
            tab === 'account' ? 'text-[#66FCF1] drop-shadow-[0_0_8px_rgba(102,252,241,0.8)]' : 'text-[#5C6B80]'
          }`}
        >
          <UserIcon className="w-5 h-5" />
          ACCOUNT
        </button>
      </nav>
    </div>
  );
}
