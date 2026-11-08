//! SigmaOS-wallpaper-engine — Wallpaper management for SigmaOS.

use std::collections::HashMap;

/// Wallpaper source
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WallpaperSource {
    /// Static image
    Image,
    /// Video wallpaper
    Video,
    /// Animated wallpaper
    Animated,
    /// Gradient
    Gradient,
}

/// Wallpaper transition
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WallpaperTransition {
    /// Instant switch
    Instant,
    /// Fade
    Fade,
    /// Slide
    Slide,
    /// Zoom
    Zoom,
    /// Wipe
    Wipe,
}

/// Monitor background
#[derive(Debug, Clone)]
pub struct MonitorBackground {
    pub output_name: String,
    pub image_path: String,
    pub source: WallpaperSource,
    pub transition: WallpaperTransition,
    pub transition_duration_ms: u32,
    pub blur_radius: u8,
    pub dim_opacity: f32,
}

impl MonitorBackground {
    pub fn new(output: &str, path: &str) -> Self {
        Self {
            output_name: output.into(),
            image_path: path.into(),
            source: WallpaperSource::Image,
            transition: WallpaperTransition::Fade,
            transition_duration_ms: 500,
            blur_radius: 0,
            dim_opacity: 0.0,
        }
    }
}

/// Wallpaper manager
#[derive(Debug, Default)]
pub struct WallpaperManager {
    backgrounds: HashMap<String, MonitorBackground>,
    slideshow_interval_secs: u64,
    slideshow_enabled: bool,
}

impl WallpaperManager {
    pub fn new() -> Self { Self::default() }

    /// Set background for a monitor
    pub fn set_background(&mut self, output: &str, path: &str) {
        let mut bg = MonitorBackground::new(output, path);
        if let Some(existing) = self.backgrounds.get(output) {
            bg.source = existing.source.clone();
            bg.transition = existing.transition.clone();
            bg.transition_duration_ms = existing.transition_duration_ms;
            bg.blur_radius = existing.blur_radius;
            bg.dim_opacity = existing.dim_opacity;
        }
        self.backgrounds.insert(output.into(), bg);
    }

    /// Set background with full config
    pub fn set_background_configured(&mut self, bg: MonitorBackground) {
        self.backgrounds.insert(bg.output_name.clone(), bg);
    }

    /// Get image for output
    pub fn get_image(&self, output: &str) -> Option<&str> {
        self.backgrounds.get(output).map(|b| b.image_path.as_str())
    }

    /// Get background config
    pub fn get_background(&self, output: &str) -> Option<&MonitorBackground> {
        self.backgrounds.get(output)
    }

    /// Remove background
    pub fn remove_background(&mut self, output: &str) -> bool {
        self.backgrounds.remove(output).is_some()
    }

    /// List all outputs
    pub fn list_outputs(&self) -> Vec<&str> {
        self.backgrounds.keys().map(|s| s.as_str()).collect()
    }

    /// Enable slideshow
    pub fn enable_slideshow(&mut self, interval_secs: u64) {
        self.slideshow_enabled = true;
        self.slideshow_interval_secs = interval_secs;
    }

    /// Disable slideshow
    pub fn disable_slideshow(&mut self) {
        self.slideshow_enabled = false;
    }

    /// Check if slideshow active
    pub fn is_slideshow_active(&self) -> bool {
        self.slideshow_enabled
    }

    /// Get slideshow interval
    pub fn slideshow_interval(&self) -> u64 {
        self.slideshow_interval_secs
    }

    /// Set blur for output
    pub fn set_blur(&mut self, output: &str, radius: u8) -> bool {
        if let Some(bg) = self.backgrounds.get_mut(output) {
            bg.blur_radius = radius;
            return true;
        }
        false
    }

    /// Set dim for output
    pub fn set_dim(&mut self, output: &str, opacity: f32) -> bool {
        if let Some(bg) = self.backgrounds.get_mut(output) {
            bg.dim_opacity = opacity.clamp(0.0, 1.0);
            return true;
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wallpaper_assignment() {
        let mut mgr = WallpaperManager::new();
        mgr.set_background("DP-1", "/usr/share/wallpapers/sigma-dark.png");
        assert_eq!(mgr.get_image("DP-1"), Some("/usr/share/wallpapers/sigma-dark.png"));
    }

    #[test]
    fn test_multiple_monitors() {
        let mut mgr = WallpaperManager::new();
        mgr.set_background("DP-1", "/wallpapers/a.png");
        mgr.set_background("HDMI-A-1", "/wallpapers/b.png");
        
        assert_eq!(mgr.get_image("DP-1"), Some("/wallpapers/a.png"));
        assert_eq!(mgr.get_image("HDMI-A-1"), Some("/wallpapers/b.png"));
        assert_eq!(mgr.list_outputs().len(), 2);
    }

    #[test]
    fn test_overwrite_background() {
        let mut mgr = WallpaperManager::new();
        mgr.set_background("DP-1", "/old.png");
        mgr.set_background("DP-1", "/new.png");
        
        assert_eq!(mgr.get_image("DP-1"), Some("/new.png"));
        assert_eq!(mgr.list_outputs().len(), 1);
    }

    #[test]
    fn test_remove_background() {
        let mut mgr = WallpaperManager::new();
        mgr.set_background("DP-1", "/wall.png");
        
        assert!(mgr.remove_background("DP-1"));
        assert_eq!(mgr.get_image("DP-1"), None);
        assert!(!mgr.remove_background("DP-1"));
    }

    #[test]
    fn test_configured_background() {
        let mut mgr = WallpaperManager::new();
        let bg = MonitorBackground {
            output_name: "eDP-1".into(),
            image_path: "/wp.jpg".into(),
            source: WallpaperSource::Video,
            transition: WallpaperTransition::Slide,
            transition_duration_ms: 1000,
            blur_radius: 10,
            dim_opacity: 0.3,
        };
        mgr.set_background_configured(bg);
        
        let got = mgr.get_background("eDP-1").unwrap();
        assert_eq!(got.source, WallpaperSource::Video);
        assert_eq!(got.blur_radius, 10);
        assert!((got.dim_opacity - 0.3).abs() < 0.01);
    }

    #[test]
    fn test_slideshow() {
        let mut mgr = WallpaperManager::new();
        assert!(!mgr.is_slideshow_active());
        
        mgr.enable_slideshow(300);
        assert!(mgr.is_slideshow_active());
        assert_eq!(mgr.slideshow_interval(), 300);
        
        mgr.disable_slideshow();
        assert!(!mgr.is_slideshow_active());
    }

    #[test]
    fn test_blur_dim() {
        let mut mgr = WallpaperManager::new();
        mgr.set_background("DP-1", "/wp.png");
        
        assert!(mgr.set_blur("DP-1", 20));
        assert!(mgr.set_dim("DP-1", 0.5));
        
        let bg = mgr.get_background("DP-1").unwrap();
        assert_eq!(bg.blur_radius, 20);
        assert!((bg.dim_opacity - 0.5).abs() < 0.01);
        
        // Dim clamps to [0,1]
        mgr.set_dim("DP-1", 2.0);
        assert!((mgr.get_background("DP-1").unwrap().dim_opacity - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_missing_output() {
        let mut mgr = WallpaperManager::new();
        assert_eq!(mgr.get_image("DP-99"), None);
        assert!(!mgr.set_blur("DP-99", 10));
        assert!(!mgr.set_dim("DP-99", 0.5));
    }
}
