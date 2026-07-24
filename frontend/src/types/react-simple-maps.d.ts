declare module "react-simple-maps" {
  import type { ComponentType, ReactNode } from "react";

  interface ComposableMapProps {
    projection?: string;
    projectionConfig?: { scale?: number; center?: [number, number] };
    style?: Record<string, string | number>;
    children?: ReactNode;
  }

  interface GeographiesProps {
    geography: string | Record<string, any>;
    children: (data: { geographies: any[] }) => ReactNode;
  }

  interface GeographyProps {
    geography: any;
    style?: {
      default?: Record<string, string | number>;
      hover?: Record<string, string | number>;
      pressed?: Record<string, string | number>;
    };
  }

  interface MarkerProps {
    coordinates: [number, number];
    onMouseEnter?: (e: any) => void;
    onMouseLeave?: () => void;
    onClick?: () => void;
    children?: ReactNode;
  }

  export const ComposableMap: ComponentType<ComposableMapProps>;
  export const Geographies: ComponentType<GeographiesProps>;
  export const Geography: ComponentType<GeographyProps>;
  export const Marker: ComponentType<MarkerProps>;
}
