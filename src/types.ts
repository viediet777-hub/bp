export interface Product {
  product_id: number;
  catalog_id?: number;
  name: string;
  price: number;
  fod_price?: number;
  fod_savings?: string;
  original_price: number;
  mrp: number;
  discount_text?: string;
  rating?: {
    average: number;
    count: number;
  };
  rating_value?: number;
  image: string;
  images?: string[];
  sizes?: {
    name: string;
    id: number;
    in_stock?: boolean;
  }[];
  supplier_id?: number;
  supplier_name?: string;
  in_stock?: boolean;
}

export interface CartItem {
  id: string | number;
  product_id: number;
  supplier_id?: number;
  variation_id?: number;
  variation_name?: string;
  name: string;
  price: number;
  mrp: number;
  image: string;
  qty: number;
}

export interface Address {
  id: number;
  name: string;
  mobile: string;
  pin: string;
  city: string;
  state: string;
  address_line_1: string;
  is_default: boolean;
}

export interface Order {
  order_num: string;
  meesho_order_num?: string;
  items_text: string;
  total: number;
  status: 'pending' | 'confirmed' | 'delivered' | 'cancelled';
  payment_method: 'COD' | 'UPI';
  created_at: number;
  address?: string;
}

export interface FODOffer {
  title: string;
  text: string;
  subtitle: string;
  bucket: number;
  display_bucket: number;
  display_text: string;
  duration?: number;
  live?: boolean;
}
