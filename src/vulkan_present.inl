VkPresentModeKHR uncappedPresentMode() {
    uint32_t count = 0;
    vkcheck(vkGetPhysicalDeviceSurfacePresentModesKHR(physical, surface, &count, nullptr), "Present mode count");
    std::vector<VkPresentModeKHR> modes(count);
    vkcheck(vkGetPhysicalDeviceSurfacePresentModesKHR(physical, surface, &count, modes.data()), "Present modes");
    modes.resize(count);
    for (auto mode : {VK_PRESENT_MODE_IMMEDIATE_KHR, VK_PRESENT_MODE_MAILBOX_KHR}) {
        if (std::find(modes.begin(), modes.end(), mode) != modes.end()) {
            rendererInfo["present_mode"] = mode == VK_PRESENT_MODE_IMMEDIATE_KHR ? "immediate" : "mailbox";
            rendererInfo["uncapped_available"] = true;
            return mode;
        }
    }
    // Keep the fixture usable, but never report FIFO as uncapped measurement.
    rendererInfo["present_mode"] = "fifo";
    rendererInfo["uncapped_available"] = false;
    return VK_PRESENT_MODE_FIFO_KHR;
}
