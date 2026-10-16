#pragma once
#include <dxgi1_5.h>

bool allowTearing = false;
void configureUncappedPresent(IDXGIFactory4* factory, DXGI_SWAP_CHAIN_DESC1& description) {
    ComPtr<IDXGIFactory5> modern;
    BOOL supported = FALSE;
    if (SUCCEEDED(factory->QueryInterface(IID_PPV_ARGS(&modern))) &&
        SUCCEEDED(modern->CheckFeatureSupport(DXGI_FEATURE_PRESENT_ALLOW_TEARING,
                                              &supported, sizeof(supported))) && supported) {
        description.Flags |= DXGI_SWAP_CHAIN_FLAG_ALLOW_TEARING;
        allowTearing = true;
    }
    rendererInfo["sync_interval"] = 0;
    rendererInfo["allow_tearing"] = allowTearing;
}
