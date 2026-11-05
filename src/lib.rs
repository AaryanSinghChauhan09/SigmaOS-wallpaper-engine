#[derive(Debug, Clone)]
pub struct MonitorBackground {
    pub output_name: String,
    pub image_path: String,
}

#[derive(Debug, Default)]
pub struct WallpaperManager {
    backgrounds: Vec<MonitorBackground>,
}

impl WallpaperManager {
    pub fn new() -> Self { Self::default() }
    pub fn set_background(&mut self, output: &str, path: &str) {
        self.backgrounds.push(MonitorBackground {
            output_name: output.to_string(),
            image_path: path.to_string(),
        });
    }
    pub fn get_image(&self, output: &str) -> Option<&str> {
        self.backgrounds.iter().find(|b| b.output_name == output).map(|b| b.image_path.as_str())
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
}
