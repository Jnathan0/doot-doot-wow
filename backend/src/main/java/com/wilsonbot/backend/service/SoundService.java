package com.wilsonbot.backend.service;

import com.wilsonbot.backend.entity.Sound;
import com.wilsonbot.backend.dao.SoundRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

@Service("soundService")
public class SoundService {
    @Autowired
    private SoundRepository soundRepository;

    public Sound getByName(String sound_id){
        return soundRepository.findByName(sound_id);
    }

    // public Page<User> findPage(){
    //     Pageable pageable = PageRequest.of(0, 10);
    //     return userRepository. findAll(pageable);
    // }

    // public Page<User> find(Long maxId){
    //     Pageable pageable = PageRequest.of(0, 10);
    //     return userRepository.findMore(maxId,pageable);
    // }

    // public User save(User u){
    //     return userRepository. save(u);
    // }

    // public User update(Long id, String name){
    //     User user = userRepository.findById(id).get();
    //     user.setName(name+"_update");
    //     return userRepository. save(user);
    // }

    // public Boolean updateById(String name, Long id){
    //     return userRepository.updateById(name,id)==1;
    // }

}