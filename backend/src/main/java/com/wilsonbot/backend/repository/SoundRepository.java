package com.wilsonbot.backend.repository;

import com.wilsonbot.backend.entity.Sound;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
// import javax.transaction.Transactional;


@Repository
public interface SoundRepository extends JpaRepository<Sound, String> {
    Sound findBySoundId(String sound_id);
}

// @Repository
// public interface SoundRepository extends JpaRepository<Sound, Long>{

//     //Optional<User> is provided by default findById(Long id);

//     Sound findByName(String name);

//     @Query("SELECT * FROM sounds;")
//     Page<Sound> findMore(String maxId, Pageable pageable);

//     // @Modifying
//     // @Transactional
//     // @Query("update User u set u.name = ?1 where u.id = ?2")
//     // int updateById(String name, Long id);


// }